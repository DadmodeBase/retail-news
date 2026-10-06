"""
neta_gatherer.py
日刊リテールニュース自動配信システム メインエントリポイント

全体の流れ:
  1. note RSS から過去記事を同期（retail_url_mapping.md の更新）
  2. 重複実行ガード（GitHub Actions上で当日レポートが既にあればスキップ）
  3. RSSフィードからニュース収集（新規オープン・イベント等はコード側で完全除外）
  4. Gemini でレポート本文・記事タイトルを生成
  5. ヘッダー画像の準備 & ローカル保存
  6. note へ自動投稿（タグ設定・マガジン追加・公開後API検証・自動修復）
  7. X（Twitter）投稿案の生成
  8. メール送信（レポート添付、note URL、X投稿案）
  9. GitHub Actions 上でレポートをリポジトリへ自動コミット＆プッシュ
"""

import datetime
import os
import sys
import traceback

import config
import content_generator
import news_fetcher
import note_publisher
import storage


def validate_environment():
    """必要な環境変数が設定されているか確認"""
    required = {
        "GEMINI_API_KEY": config.GEMINI_API_KEY,
        "EMAIL_SENDER": config.EMAIL_SENDER,
        "EMAIL_PASSWORD": config.EMAIL_PASSWORD,
        "EMAIL_RECEIVER": config.EMAIL_RECEIVER,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"[警告] 以下の環境変数が設定されていません: {', '.join(missing)}")
    else:
        print("[OK] 基本的な環境変数の設定を確認しました。")


def main():
    try:
        validate_environment()

        # 1. note記事の自動同期（X投稿案の過去記事参照用）
        storage.sync_note_articles()

        now_jst = datetime.datetime.now(config.JST)
        date_str = now_jst.strftime("%Y-%m-%d")
        weekday = now_jst.weekday()  # 0=Mon ... 6=Sun

        # 2. 重複実行ガード（GitHub Actions環境での多重投稿・再実行防止）
        if config.IS_GITHUB_ACTIONS:
            storage.git_pull()
            existing_report = os.path.join(config.REPORTS_DIR, f"{date_str}-daily-report.md")
            if os.path.exists(existing_report):
                print(f"[スキップ] 本日分（{date_str}）のレポートは既に生成・保存済みです。")
                return

            # note 側の公開状況もチェック（Git未反映時の多重投稿防止）
            published_note = note_publisher.check_today_published_on_note(date_str)
            if published_note:
                print(f"[スキップ] noteに本日分（{date_str}）の記事が既に公開されています: {published_note.get('url')}")
                return

        # 3. Google Driveから過去記事タイトルの履歴を取得（重複ピックアップ防止）
        service = storage.get_drive_service() if config.DRIVE_FOLDER_ID else None
        history, file_id = storage.load_history(service) if service else ([], None)

        # 4. レポート生成
        if weekday == 6:
            # 日曜日: 週間まとめ
            outputs = content_generator.generate_weekly_summary(now_jst)
            fetched_articles = []
        else:
            # 平日・土曜: 通常デイリーレポート
            feeds, target_days = config.FEEDS_BY_WEEKDAY.get(weekday, (config.ALL_FALLBACK_FEEDS, 1))
            fetched_articles = news_fetcher.fetch_latest_news(
                feeds=feeds,
                target_days=target_days,
                history=history,
                now_jst=now_jst,
            )
            if not fetched_articles:
                print("対象となる新しい記事がないため終了します。")
                return

            outputs = content_generator.generate_daily_report(fetched_articles)

            # 処理した記事タイトルを履歴に追加・保存
            if service and history is not None:
                new_titles = [a["title"] for a in fetched_articles]
                history.extend(new_titles)
                storage.save_history(service, history, file_id)

        if not outputs:
            print("[エラー] レポートの生成に失敗しました。")
            return

        article_title = outputs.get("article_title", f"【日刊】リテール最新トレンド - {date_str}")
        daily_report = outputs.get("daily_report", "")

        # 5. ファイル保存
        os.makedirs(config.REPORTS_DIR, exist_ok=True)
        md_report_path = os.path.join(config.REPORTS_DIR, f"{date_str}-daily-report.md")
        with open(md_report_path, "w", encoding="utf-8") as f:
            f.write(daily_report)

        header_path = os.path.join(config.REPORTS_DIR, f"{date_str}-header.png")
        header_result = storage.prepare_header_image(date_str, header_path)

        attachments = [md_report_path]
        if header_result and os.path.exists(header_result):
            attachments.append(header_result)

        # 6. note への自動投稿（Cookie設定がある場合のみ）
        note_url = ""
        tags = content_generator.build_note_tags(article_title)
        print(f"設定対象ハッシュタグ: {tags}")
        print(f"設定対象マガジン: {config.NOTE_MAGAZINE_NAME}")

        try:
            pub_result = note_publisher.publish_with_verification(
                title=article_title,
                body_text=daily_report,
                header_image_path=header_result,
                tags=tags,
                magazine_name=config.NOTE_MAGAZINE_NAME,
                magazine_key=config.NOTE_MAGAZINE_KEY,
                headless=True,
            )
            if pub_result.get("success"):
                note_url = pub_result.get("url", "")
                print(f"[OK] noteへの自動投稿が完了しました: {note_url}")
            else:
                print(f"[注意] note自動投稿がスキップまたは失敗しました: {pub_result.get('message')}")
        except Exception as e:
            print(f"[注意] note自動投稿処理で例外が発生しました（後続処理は継続します）: {e}")
            traceback.print_exc()

        # note投稿直後にもレポートをGitへコミット＆プッシュ（後続処理で万一ハングしても多重投稿を確実に防ぐ）
        storage.git_commit_and_push(
            paths=[f"content/reports/{date_str}-daily-report.md"],
            message=f"auto: save daily report {date_str}",
        )

        # 7. X（Twitter）投稿案の生成
        x_posts_text = ""
        try:
            x_posts_text = content_generator.generate_x_posts(daily_report, today_url=note_url)
        except Exception as e:
            print(f"[注意] X投稿案の生成で例外が発生しました（メール送信は継続します）: {e}")

        # 8. メール送信
        email_body = "本日のレポートを添付します。\n\n"
        if note_url:
            email_body += f"【公開済み note URL】\n{note_url}\n\n"
        if x_posts_text:
            email_body += x_posts_text

        try:
            storage.send_email(
                subject=f"【日刊】{article_title} - {date_str}",
                body=email_body,
                attachment_paths=attachments,
            )
        except Exception as e:
            print(f"[エラー] メール送信に失敗しました: {e}")
            traceback.print_exc()

        print("[OK] すべての工程が正常に完了しました。")

    except Exception as e:
        print(f"[致命的エラー] 処理全体で例外が発生しました: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

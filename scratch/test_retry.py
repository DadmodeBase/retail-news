import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from skills.neta_gatherer.neta_gatherer import generate_content_with_retry

class DummyModels:
    def __init__(self):
        self.call_count = 0

    def generate_content(self, model, contents, config=None):
        self.call_count += 1
        if self.call_count < 3:
            # 503エラーを模擬
            raise Exception("503 UNAVAILABLE: This model is currently experiencing high demand.")
        else:
            class DummyResponse:
                text = "Success Response"
            return DummyResponse()

class DummyClient:
    def __init__(self):
        self.models = DummyModels()

def main():
    client = DummyClient()
    print("Testing generate_content_with_retry...")
    try:
        response = generate_content_with_retry(
            client=client,
            model="gemini-3.5-flash",
            contents="test prompt",
            max_retries=5,
            delay=1
        )
        print(f"Result: {response.text}")
        print(f"Call count (should be 3): {client.models.call_count}")
        if response.text == "Success Response" and client.models.call_count == 3:
            print("TEST PASSED")
        else:
            print("TEST FAILED")
    except Exception as e:
        print(f"Test failed with exception: {e}")

if __name__ == "__main__":
    main()

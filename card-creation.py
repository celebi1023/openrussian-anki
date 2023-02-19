import sys
import json
import urllib.request
from selenium import webdriver
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

word = word = sys.argv[1] if len(sys.argv) > 1 else input("Input word: ")
chrome_driver_path = r"../drivers/chromedriver_win32/chromedriver.exe"

# make chrome log requests
capabilities = DesiredCapabilities.CHROME
capabilities["goog:loggingPrefs"] = {"performance": "ALL"}

chrome_options = Options()
chrome_options.add_experimental_option("w3c", False)

driver = webdriver.Chrome(
    desired_capabilities=capabilities, executable_path=chrome_driver_path
)

driver.get("https://en.openrussian.org/ru/" + word)
# extract word with stress
bare = driver.find_element(By.CLASS_NAME, "bare")
word_with_stress = bare.find_element(By.XPATH, "./h1/span[1]").text
print(word_with_stress)

overview = driver.find_element(By.CLASS_NAME, "overview").text
translations = driver.find_element(By.CLASS_NAME, "section.translations").text

# word usage
usage = None
try:
    usage = driver.find_element(By.CLASS_NAME, "section.usage").text
except NoSuchElementException:
    print("No usage found.")

# conjugation (only for verbs)
conjugation = None
try:
    conjugation = driver.find_element(By.CLASS_NAME, "section.verb.conjugation").text
except NoSuchElementException:
    print("No conjugation found.")

# pronunciation
audio = driver.find_element(By.CLASS_NAME, "jsx.read.auto.icon.icon-play")
audio.click()

# extract requests from logs
logs_raw = driver.get_log("performance")
logs = [json.loads(lr["message"])["message"] for lr in logs_raw]

audio_api_addr = r"https://api.openrussian.org/read/ru/"


def is_audio_request(log):
    if "request" not in log["params"] or "url" not in log["params"]["request"]:
        return False
    url = log["params"]["request"]["url"]
    return (
        len(url) >= len(audio_api_addr) and url[: len(audio_api_addr)] == audio_api_addr
    )


audio_logs = [log for log in filter(is_audio_request, logs)]
audio_url = None
if len(audio_logs) > 0:
    audio_url = audio_logs[-1]["params"]["request"]["url"]
else:
    print("audio not found")

driver.close()


# create anki card
def request(action, **params):
    return {"action": action, "params": params, "version": 6}


def invoke(action, **params):
    requestJson = json.dumps(request(action, **params)).encode("utf-8")
    response = json.load(
        urllib.request.urlopen(
            urllib.request.Request("http://localhost:8765", requestJson)
        )
    )
    if len(response) != 2:
        raise Exception("response has an unexpected number of fields")
    if "error" not in response:
        raise Exception("response is missing required error field")
    if "result" not in response:
        raise Exception("response is missing required result field")
    if response["error"] is not None:
        raise Exception(response["error"])
    return response["result"]


# create card content
content = ""
content += word_with_stress
if len(overview) > 0:
    content += "\n\n" + overview
content += "\n\n" + translations
if usage:
    content += "\n\n" + usage
if conjugation:
    content += "\n\n" + conjugation
content = content.replace("\n", "<br>")

result = invoke(
    "addNotes",
    notes=[
        {
            "deckName": "Mining - Russian",
            "modelName": "Basic",
            "fields": {"Front": word, "Back": content},
            "tags": ["script"],
            "audio": [
                {"url": audio_url, "filename": word + ".mp3", "fields": ["Back"]}
            ],
        }
    ],
)
if result[0]:
    print("Successfully added card to deck.")
else:
    print("Failed to add card to deck.")

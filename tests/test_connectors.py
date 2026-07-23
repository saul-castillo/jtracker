import unittest

from jtracker.connectors import workday


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeWorkdaySession:
    def __init__(self, total=105):
        self.total = total
        self.offsets = []
        self.detail_paths = []

    def post(self, _url, json, timeout):
        del timeout
        offset = json["offset"]
        limit = json["limit"]
        self.offsets.append(offset)
        page = [
            {
                "title": f"Engineering Intern {index}",
                "locationsText": "Austin, TX",
                "externalPath": f"/job/{index}",
            }
            for index in range(offset, min(offset + limit, self.total))
        ]
        return FakeResponse({"total": self.total, "jobPostings": page})

    def get(self, url, timeout):
        del timeout
        path = "/" + url.rsplit("/", 2)[-2] + "/" + url.rsplit("/", 1)[-1]
        self.detail_paths.append(path)
        index = path.rsplit("/", 1)[-1]
        return FakeResponse(
            {
                "jobPostingInfo": {
                    "jobReqId": f"REQ-{index}",
                    "title": f"Electrical Engineering Intern {index}",
                    "location": "Austin, TX",
                    "jobDescription": "<p>Summer 2027 analog circuit design.</p>",
                    "postedOn": "Posted Today",
                    "jobRequisitionLocation": {
                        "country": {"alpha2Code": "US"}
                    },
                }
            }
        )


class WorkdayTests(unittest.TestCase):
    def test_paginates_past_100_and_fetches_descriptions(self):
        session = FakeWorkdaySession(total=105)
        source = {
            "company": "Example",
            "kind": "workday",
            "platform": "Workday",
            "endpoint": (
                "https://example.wd1.myworkdayjobs.com/wday/cxs/"
                "example/External/jobs"
            ),
        }

        result = workday(source, session)

        self.assertEqual(len(result.jobs), 105)
        self.assertIn(100, session.offsets)
        self.assertEqual(len(session.detail_paths), 105)
        self.assertEqual(
            result.jobs[-1]["description"], "Summer 2027 analog circuit design."
        )
        self.assertEqual(result.jobs[-1]["country_code"], "US")


if __name__ == "__main__":
    unittest.main()

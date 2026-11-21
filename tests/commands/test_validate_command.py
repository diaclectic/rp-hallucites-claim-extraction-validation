import json
import urllib.error
import urllib.request

import pytest

from claimcheck.commands.validate_command import ValidateCommand


@pytest.fixture
def served(config):
    command = ValidateCommand(config, open_browser=False)
    command.dataset.load()
    command.results.load()
    command.server.start()
    yield command
    command.server.close()


def call(command, method, path, body=None, headers=None):
    request = urllib.request.Request(
        command.server.url.rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.headers["Content-Type"], response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"], error.read()


def test_lists_papers_with_their_status(served):
    status, _, body = call(served, "GET", "/api/papers")
    data = json.loads(body)
    assert status == 200 and data["reviewer"] == "Test Reviewer"
    assert [(p["doc_id"], p["split"], p["status"]) for p in data["papers"]] == [
        ("2020.acl-demos.1", "dev", "todo"),
        ("2021.acl-long.2", "validation", "todo"),
    ]


def test_paper_has_highlights_and_references(served):
    _, _, body = call(served, "GET", "/api/paper/2020.acl-demos.1")
    paper = json.loads(body)
    assert len(paper["spans"]) == 4 and len(paper["references"]) == 4
    assert paper["result"] is None


def test_pdf_is_served_as_pdf(served):
    status, content_type, body = call(served, "GET", "/api/pdf/2021.acl-long.2")
    assert (status, content_type) == (200, "application/pdf")
    assert body.startswith(b"%PDF")


def test_save_writes_the_results_file_and_marks_the_paper(served, config):
    finding = {"kind": "missed", "text": "(Lost, 2001)", "context": "ctx"}
    status, _, body = call(served, "POST", "/api/result", {"doc_id": "2020.acl-demos.1", "findings": [finding], "note": "n"})
    assert status == 200 and json.loads(body)["status"] == "issues"
    saved = [json.loads(line) for line in config.results_path.read_text().splitlines()]
    assert saved[0]["findings"][0]["text"] == "(Lost, 2001)"
    papers = json.loads(call(served, "GET", "/api/papers")[2])["papers"]
    assert papers[0]["status"] == "issues"
    assert json.loads(call(served, "GET", "/api/paper/2020.acl-demos.1")[2])["result"]["note"] == "n"


def test_a_restarted_tool_resumes(served, config):
    call(served, "POST", "/api/result", {"doc_id": "2021.acl-long.2", "findings": []})
    again = ValidateCommand(config, open_browser=False)
    again.dataset.load()
    again.results.load()
    again.server.start()
    try:
        papers = json.loads(call(again, "GET", "/api/papers")[2])["papers"]
        assert [p["status"] for p in papers] == ["todo", "ok"]
    finally:
        again.server.close()


@pytest.mark.parametrize(
    "body, status",
    [
        ({"findings": []}, 400),
        ({"doc_id": "2020.acl-demos.1", "findings": [{"kind": "x", "text": "y"}]}, 400),
        ({"doc_id": "unknown", "findings": []}, 404),
    ],
)
def test_save_rejects_bad_requests(served, body, status):
    assert call(served, "POST", "/api/result", body)[0] == status


def test_unknown_paper_and_pdf_are_404(served):
    assert call(served, "GET", "/api/paper/nope")[0] == 404
    assert call(served, "GET", "/api/pdf/..%2Fdev")[0] == 404


def test_other_host_and_origin_are_refused(served):
    assert call(served, "GET", "/api/papers", headers={"Host": "evil.example"})[0] == 403
    assert call(served, "POST", "/api/finish", {}, headers={"Origin": "http://evil.example"})[0] == 403


def test_static_page_and_script_are_served(served):
    assert call(served, "GET", "/")[0] == 200
    assert call(served, "GET", "/validate.js")[1].startswith("text/javascript")
    assert call(served, "GET", "/../config.py")[0] == 404

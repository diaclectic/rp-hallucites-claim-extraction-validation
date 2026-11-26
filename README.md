# claimcheck

A local browser tool for reviewing the claim-extraction dev and validation sets. Each paper's text is shown with every
citation in the reference set highlighted, beside the original PDF. You skim for what is wrong and flag it:

- **Missed citation**: a citation in the text that is not highlighted. Select the text and choose *Missed citation*.
- **Not a citation**: a highlight that is not a citation. Click it.
- **Link is wrong**: a citation linked to the wrong bibliography entry. Click it, then click the right entry in the references.
- **Citance is cut off or incomplete**: click the citation and choose it.

Hovering a highlight shows the bibliography entries it links to. Papers saved with no flags count as OK.

## Install

You need Python 3.10 or newer and [pipx](https://pipx.pypa.io). Works on macOS, Linux and Windows.

```bash
brew install pipx                     # macOS
py -m pip install --user pipx         # Windows (PowerShell), then: py -m pipx ensurepath
```

```bash
pipx install /path/to/this/folder     # or: pipx install git+<repo url>
```

On Windows, open a new terminal after `ensurepath` so `pipx` and `claimcheck` are on your PATH.

## Data

The papers and PDFs are about 1 GB and come as `claimcheck_data.zip`, not through git. Extract it into your home folder
so that `claimcheck_data` is directly inside it (`~/claimcheck_data` on macOS and Linux,
`C:\Users\<you>\claimcheck_data` on Windows):

```bash
unzip claimcheck_data.zip -d ~                                  # macOS, Linux
```
```powershell
Expand-Archive claimcheck_data.zip -DestinationPath $HOME       # Windows
```

## Review

```bash
claimcheck
```

It opens the page in your browser. Work through the papers in either set (`dev`, `validation`) and press
**Save & next** on each. Progress is saved to `manual_validation_results.jsonl` in that folder after every save,
so you can stop at any time and run `claimcheck` again to carry on where you left off. When you are done, press
**Finish & close** and email that file back.

The reviewer name recorded in the results is in `claimcheck/reviewer.txt`. Change it before installing if someone else
is reviewing.

## Results format

One JSON line per reviewed paper:

```json
{"doc_id": "2020.acl-demos.18", "split": "dev", "reviewer": "Neil Mathias", "reviewed_at": "2026-11-21T15:04:05+00:00",
 "status": "issues", "findings": [{"kind": "missed", "text": "(Doe, 2020)", "context": "...", "work": "",
 "correct_entry": "", "note": ""}], "note": ""}
```

`kind` is `missed`, `wrong_citation`, `bad_link` or `bad_citance`. `status` is `issues` if there are findings and `ok` if not.

## Development

```bash
pipx install --editable .
pipx runpip claimcheck install pytest ruff
"$(pipx environment --value PIPX_LOCAL_VENVS)/claimcheck/bin/python" -m pytest
```

The server listens only on 127.0.0.1 and refuses other Host and Origin headers. The tool has no dependencies beyond the
standard library.

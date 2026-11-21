from claimcheck.process.citation_locator import CitationLocator


def test_clean_strips_markdown_and_keeps_paragraphs():
    text = CitationLocator().clean("A [link \\(x\\)](http://u) **bold**<br>and <sup>1</sup>&amp; more\nwrapped.\n\n\n\nNext")
    assert text == "A link (x) bold and 1& more wrapped.\n\nNext"


def test_locates_citations_with_offsets(paper_a):
    record, source = paper_a
    paper = CitationLocator().locate("2020.acl-demos.1", "dev", record, source)
    assert [(s["surface"], paper.text[s["start"] : s["end"]]) for s in paper.spans] == [
        ("(Papineni et al., 2002)",) * 2,
        ("(Banerjee and Lavie, 2005)",) * 2,
        ("Smith et al. (2019a)",) * 2,
        ("(Doe, 2020)",) * 2,
    ]


def test_reports_citations_missing_from_the_text(paper_a):
    record, source = paper_a
    assert CitationLocator().locate("x", "dev", record, source).unlocated == ["(Never Appears, 1999)"]


def test_links_each_citation_to_its_bibliography_entries(paper_a):
    record, source = paper_a
    paper = CitationLocator().locate("x", "dev", record, source)
    works = {s["surface"]: s["works"] for s in paper.spans}
    assert works["(Papineni et al., 2002)"][0]["refs"] == [0]
    assert works["(Banerjee and Lavie, 2005)"][0]["refs"] == [1]
    assert works["Smith et al. (2019a)"][0]["refs"] == [2]  # not the 2019b entry
    assert works["(Doe, 2020)"][0]["entry"] is None


def test_longest_span_wins_when_citations_overlap():
    record = {
        "citations": [{"surface": "Chang (2011)", "count": 1}, {"surface": "Chapelle and Chang (2011)", "count": 1}],
        "links": [],
    }
    source = {"sections": [["T", "See Chapelle and Chang (2011) here."]], "references": ""}
    paper = CitationLocator().locate("x", "dev", record, source)
    assert [s["surface"] for s in paper.spans] == ["Chapelle and Chang (2011)"]


def test_does_not_match_inside_a_longer_word():
    record = {"citations": [{"surface": "Li (2020)", "count": 1}], "links": []}
    source = {"sections": [["T", "Bali (2020) and Li (2020)."]], "references": ""}
    paper = CitationLocator().locate("x", "dev", record, source)
    assert [paper.text[s["start"] : s["end"]] for s in paper.spans] == ["Li (2020)"]
    assert paper.spans[0]["start"] > 10


def test_suffix_keys_only_match_their_own_year_letter():
    cites = CitationLocator()._cites
    link_b = {"key": ["smith", "2019b"]}
    assert not cites("Smith et al. (2019a)", link_b)
    assert cites("(Smith, 2019a,b)", link_b)
    assert not cites("(Smith, 2019)", link_b)


def test_last_name_must_be_a_whole_word():
    cites = CitationLocator()._cites
    link = {"key": ["ma", "2019"]}
    assert not cites("(Zhu and Wang, 2006; Nie, 2010; Yarmohammadi et al., 2019)", link)
    assert cites("(Ma et al., 2019)", link)
    assert cites("(Stanojević and Sima'an, 2014)", {"key": ["simaan", "2014"]})
    assert cites("Shi2019", {"key": ["shi", "2019"]})

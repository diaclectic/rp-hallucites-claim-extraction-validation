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


def test_name_and_year_must_be_in_the_same_item():
    cites = CitationLocator()._cites
    zhang = {"key": ["zhang", "2015"]}
    assert not cites("(Vo and Zhang, 2015; Zhang et al., 2016; Alghunaim et al., 2015)", zhang, first_author=True)
    assert cites("(Vo and Zhang, 2015; Zhang et al., 2015)", zhang, first_author=True)
    assert not cites("(Chung et al., 2016; Luong and Manning, 2016; Sennrich et al., 2015b)", {"key": ["luong", "2015b"]})
    assert not cites("(Luong et al., 2015a; Caglayan et al., 2016)", {"key": ["luong", "2016"]})
    assert not cites("(Bohus and Rudnicky, 2009; Ultes et al., 2017)", {"key": ["bohus", "2017"]})
    assert not cites("(Levitan et al., 2012; Lee et al., 2011)", {"key": ["levitan", "2011"]})


def test_a_later_author_loses_to_a_first_author_with_the_same_year():
    record = {
        "citations": [{"surface": "(Vo and Zhang, 2015)", "count": 1}],
        "links": [
            {"work": "Vo and Zhang, 2015", "key": ["vo", "2015"], "entry": None},
            {"work": "Zhang et al., 2015", "key": ["zhang", "2015"], "entry": None},
        ],
    }
    source = {"sections": [["T", "See (Vo and Zhang, 2015)."]], "references": ""}
    paper = CitationLocator().locate("x", "dev", record, source)
    assert [w["work"] for w in paper.spans[0]["works"]] == ["Vo and Zhang, 2015"]


def test_a_bare_year_stays_with_the_author_before_it():
    cites = CitationLocator()._cites
    assert cites("(Smith, 2018; 2019)", {"key": ["smith", "2019"]})


def test_a_citation_split_by_a_paragraph_break_is_still_located():
    record = {"citations": [{"surface": "(Kendall et al., 2018)", "count": 1}], "links": []}
    source = {"sections": [["T", "the weighted combination (Kendall\n\net al., 2018) of the above losses"]], "references": ""}
    paper = CitationLocator().locate("x", "validation", record, source)
    assert paper.unlocated == []
    assert paper.text[paper.spans[0]["start"] : paper.spans[0]["end"]] == "(Kendall\n\net al., 2018)"


def test_links_that_share_a_key_each_cite_only_the_form_they_are_written_in():
    hirschberg = {"work": "Levitan and Hirschberg, 2011", "key": ["levitan", "2011"], "entry": "A", "status": "agree"}
    etal = {"work": "Levitan et al., 2011", "key": ["levitan", "2011"], "entry": "B", "status": "added"}
    record = {"citations": [{"surface": "(Levitan and Hirschberg, 2011; Levitan et al., 2011)", "count": 1}], "links": [hirschberg, etal]}
    source = {"sections": [["T", "x (Levitan and Hirschberg, 2011; Levitan et al., 2011) y"]], "references": ""}
    works = CitationLocator().locate("x", "dev", record, source).spans[0]["works"]
    assert sorted(w["work"] for w in works) == ["Levitan and Hirschberg, 2011", "Levitan et al., 2011"]
    cites = CitationLocator()._cites
    assert cites("(Levitan et al., 2011)", etal, form=True) and not cites("(Levitan et al., 2011)", hirschberg, form=True)
    assert cites("(Levitan and Hirschberg, 2011)", hirschberg, form=True) and not cites("(Levitan and Hirschberg, 2011)", etal, form=True)


def test_an_entry_matches_its_own_item_and_not_one_that_only_shares_the_author_list():
    authors = "Felix Hieber, Tobias Domhan, Michael Denkowski, David Vilar, Artem Sokolov, Ann Clifton, and Matt Post."
    references = [f"{authors} 2017. Sockeye: a toolkit.", f"{authors} 2018. Sockeye 2: a toolkit."]
    record = {"citations": [{"surface": "(Hieber et al., 2017)", "count": 1}],
              "links": [{"work": "Hieber et al., 2017", "key": ["hieber", "2017"], "entry": references[0], "status": "agree"}]}
    source = {"sections": [["T", "x (Hieber et al., 2017) y"]], "references": "\n\n".join(references)}
    assert CitationLocator().locate("x", "dev", record, source).spans[0]["works"][0]["refs"] == [0]


def test_an_entry_with_tags_and_a_url_still_finds_the_cleaned_bibliography_item():
    entry = "Kevin McCaney. 2015. Tool kit. Defense Systems, <https://defensesystems.com/x>. Active<sup>2</sup> learning."
    record = {"citations": [{"surface": "(McCaney, 2015)", "count": 1}],
              "links": [{"work": "McCaney, 2015", "key": ["mccaney", "2015"], "entry": entry, "status": "agree"}]}
    source = {"sections": [["T", "x (McCaney, 2015) y"]], "references": entry}
    assert CitationLocator().locate("x", "dev", record, source).spans[0]["works"][0]["refs"] == [0]


def test_clean_normalizes_like_the_reference_set_surfaces():
    clean = CitationLocator().clean
    assert clean("(Hua et al., 2019, *inter alia*) and $\\mathbf{E}$ and Bick-\nnell (2018)") == "(Hua et al., 2019, inter alia) and $mathbf{E}$ and Bicknell (2018)"


def test_a_short_entry_still_matches_its_identical_item():
    record = {"citations": [{"surface": "(Google, 2023)", "count": 1}],
              "links": [{"work": "Google, 2023", "key": ["google", "2023"], "entry": "Google. 2023. Bard. <https://x.example/>.", "status": "agree"}]}
    source = {"sections": [["T", "x (Google, 2023) y"]], "references": "Google. 2023. Bard. <https://x.example/>."}
    assert CitationLocator().locate("x", "dev", record, source).spans[0]["works"][0]["refs"] == [0]


def test_an_item_equal_to_the_entry_wins_over_a_fragment_inside_it():
    entry = "Seyedarmin Azizi and Massoud Pedram. 2025. Mambaextend: a training-free approach. In The Thirteenth International Conference on Learning Representations."
    references = [entry, "The Thirteenth International Conference on Learning Representations."]
    record = {"citations": [{"surface": "(Azizi and Pedram, 2025)", "count": 1}],
              "links": [{"work": "Azizi and Pedram, 2025", "key": ["azizi", "2025"], "entry": entry, "status": "agree"}]}
    source = {"sections": [["T", "x (Azizi and Pedram, 2025) y"]], "references": "\n\n".join(references)}
    assert CitationLocator().locate("x", "dev", record, source).spans[0]["works"][0]["refs"] == [0]


def test_a_footnote_number_does_not_stick_to_the_first_word_of_the_footnote():
    assert CitationLocator().clean("Body text.\n\n<sup>10</sup>Fowlie and Koller (2017) showed it.") == "Body text.\n\nFowlie and Koller (2017) showed it."

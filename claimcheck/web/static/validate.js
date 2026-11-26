// The review page: the paper's text with citations highlighted, its references, and the original PDF beside them.

const state = {
  papers: [],
  split: "dev",
  paper: null, // the loaded paper
  findings: [], // unsaved flags for the loaded paper
  selected: null, // index of the clicked citation in paper.spans; its citance is shaded
  pending: null, // a bad_link finding waiting for the reviewer to click the correct entry
  dirty: false,
  results_path: "",
};

const $ = (id) => document.getElementById(id);
const CONTEXT_CHARS = 400;

function visiblePapers() {
  return state.papers.filter((paper) => paper.split === state.split);
}

function renderProgress() {
  const done = state.papers.filter((paper) => paper.status !== "todo").length;
  $("progress-bar").style.width = `${(100 * done) / state.papers.length}%`;
  $("progress-text").textContent = `${done} of ${state.papers.length} papers reviewed`;
}

function renderTabs() {
  $("tabs").replaceChildren(
    ...["dev", "validation"].map((split) => {
      const papers = state.papers.filter((paper) => paper.split === split);
      const done = papers.filter((paper) => paper.status !== "todo").length;
      return el(
        "button",
        { class: `tab${split === state.split ? " active" : ""}`, type: "button", onclick: () => switchSplit(split) },
        `${split} ${done}/${papers.length}`,
      );
    }),
  );
}

function renderQueue() {
  $("queue").replaceChildren(
    ...visiblePapers().map((paper) =>
      el(
        "button",
        {
          class: `item ${paper.status}${state.paper && state.paper.doc_id === paper.doc_id ? " current" : ""}`,
          type: "button",
          onclick: () => openPaper(paper.doc_id),
        },
        el("span", { class: "dot" }),
        paper.doc_id,
      ),
    ),
  );
  renderTabs();
  renderProgress();
}

async function switchSplit(split) {
  if (!(await confirmLeave())) {
    return;
  }
  state.split = split;
  const papers = visiblePapers();
  await openPaper((papers.find((paper) => paper.status === "todo") || papers[0]).doc_id, true);
}

async function confirmLeave() {
  return !state.dirty || confirm("This paper has unsaved flags. Leave without saving?");
}

async function openPaper(docId, skipConfirm = false) {
  if (!skipConfirm && !(await confirmLeave())) {
    return;
  }
  const paper = await api("GET", `/api/paper/${encodeURIComponent(docId)}`);
  state.paper = paper;
  state.split = paper.split;
  state.findings = paper.result ? paper.result.findings : [];
  state.pending = null;
  state.selected = null;
  state.dirty = false;
  $("citance-info").textContent = "";
  $("doc-id").textContent = `${paper.doc_id} (${paper.split})`;
  $("note").value = paper.result ? paper.result.note : "";
  $("pdf").src = `/api/pdf/${encodeURIComponent(paper.doc_id)}`;
  $("notfound").replaceChildren(
    ...(paper.unlocated.length
      ? [
          el(
            "details",
            { class: "unlocated" },
            el("summary", {}, `${paper.unlocated.length} citations in the reference set were not found in the text`),
            el("ul", {}, paper.unlocated.map((surface) => el("li", {}, surface))),
          ),
        ]
      : []),
  );
  renderText();
  renderRefs();
  renderFindings();
  renderQueue();
  $("text").scrollTop = 0;
  $("refs").scrollTop = 0;
}

function renderText() {
  const { text, spans } = state.paper;
  const citance = state.selected === null ? null : spans[state.selected].citance;
  const container = $("text");
  container.replaceChildren();
  let offset = 0;
  let first = 0; // the first citation that has not ended before this paragraph
  for (const paragraph of text.split("\n\n")) {
    const end = offset + paragraph.length;
    const node = el("p", { class: paragraph.startsWith("#") ? "heading" : "" });
    const sink = citanceSink(node, citance);
    let cursor = offset;
    // A citation can run across a paragraph break (a page or column break inside it): each paragraph gets its part.
    for (let index = first; index < spans.length && spans[index].start < end; index++) {
      const span = spans[index];
      const from = Math.max(span.start, offset);
      const to = Math.min(span.end, end);
      addText(sink, text, cursor, from);
      sink.add(citationNode(span, text.slice(from, to), index), from, to - from);
      cursor = to;
    }
    addText(sink, text, cursor, end);
    while (first < spans.length && spans[first].end <= end) {
      first++;
    }
    container.append(node);
    offset = end + 2;
  }
}

// Adds a paragraph's pieces in order, putting the ones inside the selected citation's citance in one shaded span. A citation
// is never cut: it is shaded whole when it overlaps the citance.
function citanceSink(paragraph, citance) {
  let shaded = null;
  return {
    citance,
    add(child, position, length) {
      if (citance && position < citance.end && position + length > citance.start) {
        if (!shaded) {
          shaded = el("span", { class: "citance" });
          paragraph.append(shaded);
        }
        shaded.append(child);
      } else {
        shaded = null;
        paragraph.append(child);
      }
    },
  };
}

// Adds text[from:to], cut where the citance starts and ends.
function addText(sink, text, from, to) {
  const cuts = [from, to];
  if (sink.citance) {
    cuts.push(sink.citance.start, sink.citance.end);
  }
  const points = [...new Set(cuts.filter((point) => point >= from && point <= to))].sort((a, b) => a - b);
  for (let i = 0; i + 1 < points.length; i++) {
    sink.add(document.createTextNode(text.slice(points[i], points[i + 1])), points[i], points[i + 1] - points[i]);
  }
}

function citationNode(span, surface, index) {
  const flags = state.findings.filter((f) => f.text === span.surface);
  const wrong = flags.some((f) => f.kind === "wrong_citation");
  const badLink = flags.some((f) => f.kind === "bad_link");
  const badCitance = flags.some((f) => f.kind === "bad_citance");
  return el(
    "mark",
    {
      class: `cite${wrong ? " wrong" : ""}${badLink ? " badlink" : ""}${badCitance ? " badcitance" : ""}`,
      "data-index": index,
      onmouseenter: (event) => showRefs(span, event.currentTarget),
      onclick: (event) => {
        citationMenu(event, span); // reads the clicked node, so it runs before the text is redrawn
        selectCitation(index);
      },
    },
    surface,
  );
}

// Shades the citation's citance in the text and shows it under the text.
function selectCitation(index) {
  state.selected = index;
  renderText();
  const span = state.paper.spans[index];
  const mark = $("text").querySelector(`mark[data-index="${index}"]`);
  if (mark) {
    showRefs(span, mark);
  }
  $("citance-info").replaceChildren(
    el("strong", {}, "Citance: "),
    span.citance
      ? state.paper.text.slice(span.citance.start, span.citance.end).replace(/\n\n/g, " ¶ ")
      : "none recorded for this citation",
  );
}

function clearSelection() {
  if (state.selected !== null) {
    state.selected = null;
    $("citance-info").textContent = "";
    renderText();
  }
}

function renderRefs() {
  $("hover-info").textContent = "";
  $("refs").replaceChildren(
    ...state.paper.references.map((reference, index) =>
      el("p", { class: "ref", "data-index": index, onclick: () => chooseEntry(reference) }, reference),
    ),
  );
}

// The last citation hovered stays active, so you can move down and scroll the references to find each of its entries.
function showRefs(span, mark) {
  document.querySelectorAll("mark.active").forEach((node) => node.classList.remove("active"));
  mark.classList.add("active");
  const hot = new Set(span.works.flatMap((work) => work.refs));
  let first = null;
  for (const node of $("refs").children) {
    const on = hot.has(Number(node.dataset.index));
    node.classList.toggle("hot", on);
    first = first || (on ? node : null);
  }
  if (first) {
    const pane = $("refs");
    pane.scrollTop = first.offsetTop - 24;
  }
  $("hover-info").textContent = span.works.map(workInfo).join("  |  ");
}

function workInfo(work) {
  if (work.entry === null) {
    return `${work.work}: reference set says there is no bibliography entry`;
  }
  return work.refs.length ? work.work : `${work.work}: entry not found in the list below`;
}

function chooseEntry(reference) {
  if (!state.pending) {
    return;
  }
  state.pending.correct_entry = reference;
  state.pending = null;
  markDirty();
  renderFindings();
}

function context(node) {
  const paragraph = node.nodeType === Node.TEXT_NODE ? node.parentElement.closest("p") : node.closest("p");
  return paragraph ? paragraph.textContent.slice(0, CONTEXT_CHARS) : "";
}

function openPopover(event, ...buttons) {
  const popover = $("popover");
  popover.replaceChildren(...buttons);
  popover.hidden = false;
  popover.style.left = `${Math.min(event.clientX, window.innerWidth - 260)}px`;
  popover.style.top = `${event.clientY + 8}px`;
}

function closePopover() {
  $("popover").hidden = true;
}

function popoverButton(label, action) {
  return el("button", { class: "btn small", type: "button", onclick: () => { closePopover(); action(); } }, label);
}

function addFinding(finding) {
  state.findings.push(finding);
  markDirty();
  renderText();
  renderFindings();
}

function removeFinding(finding) {
  state.findings = state.findings.filter((f) => f !== finding);
  if (state.pending === finding) {
    state.pending = null;
  }
  markDirty();
  renderText();
  renderFindings();
}

function citationMenu(event, span) {
  event.stopPropagation();
  const node = event.currentTarget;
  const flagged = state.findings.filter((f) => f.text === span.surface);
  const where = context(node);
  const citance = span.citance ? state.paper.text.slice(span.citance.start, span.citance.end) : where;
  openPopover(
    event,
    ...(flagged.length
      ? [popoverButton("Clear flags", () => flagged.forEach((finding) => removeFinding(finding)))]
      : [
          popoverButton("Not a citation", () =>
            addFinding({ kind: "wrong_citation", text: span.surface, context: where, work: "", correct_entry: "", note: "" }),
          ),
          popoverButton("Citance is cut off or incomplete", () =>
            addFinding({ kind: "bad_citance", text: span.surface, context: citance, work: "", correct_entry: "", note: "" }),
          ),
          ...span.works.map((work) =>
            popoverButton(`Link is wrong: ${work.work}`, () => {
              const finding = {
                kind: "bad_link", text: span.surface, context: where, work: work.work, correct_entry: "", note: "",
              };
              state.pending = finding;
              addFinding(finding);
            }),
          ),
        ]),
  );
}

function selectionMenu(event) {
  const selection = window.getSelection();
  const selected = selection.toString().replace(/\s+/g, " ").trim();
  if (!selected || selection.rangeCount === 0 || !$("text").contains(selection.anchorNode)) {
    return;
  }
  const where = context(selection.anchorNode);
  openPopover(
    event,
    popoverButton("Missed citation", () => {
      addFinding({ kind: "missed", text: selected, context: where, work: "", correct_entry: "", note: "" });
      selection.removeAllRanges();
    }),
  );
}

const KIND_LABELS = { missed: "Missed", wrong_citation: "Not a citation", bad_link: "Wrong link", bad_citance: "Bad citance" };

function renderFindings() {
  $("findings").replaceChildren(
    ...state.findings.map((finding) =>
      el(
        "div",
        { class: `finding ${finding.kind}` },
        el("span", { class: "kind" }, KIND_LABELS[finding.kind]),
        el("span", { class: "ftext" }, finding.work ? `${finding.text} → ${finding.work}` : finding.text),
        finding === state.pending && el("em", {}, "Click the correct entry in the references"),
        finding.correct_entry && el("span", { class: "correct" }, `Correct entry: ${finding.correct_entry.slice(0, 90)}`),
        el("input", {
          type: "text", placeholder: "note", value: finding.note,
          oninput: (event) => { finding.note = event.target.value; markDirty(); },
        }),
        el("button", { class: "btn small", type: "button", onclick: () => removeFinding(finding) }, "Remove"),
      ),
    ),
  );
}

function markDirty() {
  state.dirty = true;
}

async function save() {
  const { doc_id } = state.paper;
  const result = await api("POST", "/api/result", { doc_id, findings: state.findings, note: $("note").value });
  state.papers.find((paper) => paper.doc_id === doc_id).status = result.status;
  state.dirty = false;
  renderQueue();
  step(1, true);
}

function step(direction, skipConfirm = false) {
  const papers = visiblePapers();
  const index = papers.findIndex((paper) => paper.doc_id === state.paper.doc_id) + direction;
  if (index >= 0 && index < papers.length) {
    openPaper(papers[index].doc_id, skipConfirm);
  }
}

async function finish() {
  if (!(await confirmLeave()) || !confirm("Finish and stop the tool? Your saved reviews are kept.")) {
    return;
  }
  await api("POST", "/api/finish", {});
  document.body.replaceChildren(
    el("div", { class: "done" }, el("h1", {}, "Done"), el("p", {}, `Close this tab, then email ${state.results_path}`)),
  );
}

async function main() {
  const data = await api("GET", "/api/papers");
  state.papers = data.papers;
  state.results_path = data.results_path;
  $("reviewer").textContent = `· ${data.reviewer}`;
  const first = data.papers.find((paper) => paper.status === "todo") || data.papers[0];
  $("save").addEventListener("click", save);
  $("prev").addEventListener("click", () => step(-1));
  $("next").addEventListener("click", () => step(1));
  $("finish").addEventListener("click", finish);
  $("note").addEventListener("input", markDirty);
  $("text").addEventListener("mouseup", selectionMenu);
  document.addEventListener("mousedown", (event) => {
    if (!$("popover").contains(event.target)) {
      closePopover();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePopover();
      state.pending = null;
      renderFindings();
      clearSelection();
    }
  });
  window.addEventListener("beforeunload", (event) => {
    if (state.dirty) {
      event.preventDefault();
    }
  });
  await openPaper(first.doc_id, true);
}

main().catch((error) => document.body.prepend(el("div", { class: "error" }, `Could not start: ${error.message}`)));

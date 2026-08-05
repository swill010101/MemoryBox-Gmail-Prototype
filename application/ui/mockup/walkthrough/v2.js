/* Experience Walkthrough v2.0 — cause-driven scenes for user testing */
(function () {
  const scenes = [
    {
      id: "00",
      src: "v2/media/00-title.png",
      sec: 4,
      input: "—",
      did: "Opened the walkthrough.",
      understood: "This is MemoryBox — a family memory companion.",
      changed: "Nothing in the archive yet.",
      next: "A family is home after dinner."
    },
    {
      id: "01",
      src: "v2/media/01-home.png",
      sec: 5,
      input: "Home · invite",
      did: "Sat down after dinner. Opened MemoryBox.",
      understood: "They’re ready to explore — not organize files.",
      changed: "Conversation is available.",
      next: "Someone will ask for Dad’s later-year photos."
    },
    {
      id: "02",
      src: "v2/media/02-dad-photos.png",
      sec: 8,
      input: "Voice",
      did: "Spoke: “Show me pictures of Dad from his later years.”",
      understood: "Dad · later years · photographs.",
      changed: "Dad’s later photos appear as memories — not folders.",
      next: "They’ll pick one photograph."
    },
    {
      id: "03",
      src: "v2/media/03-enlarged.png",
      sec: 5,
      input: "Touch / click",
      did: "Selected one photograph.",
      understood: "This photo is the focus now.",
      changed: "The photograph enlarges.",
      next: "A detail in the photo invites attention."
    },
    {
      id: "04",
      src: "v2/media/04-rubberband-watch.png",
      sec: 8,
      input: "Rubber-band (mouse/touch)",
      did: "Drew a selection around Grandpa’s pocket watch.",
      understood: "An object was indicated — it has no story yet.",
      changed: "Invite appears: add a story?",
      next: "They can record why the watch mattered."
    },
    {
      id: "05",
      src: "v2/media/05-voice-story.png",
      sec: 10,
      input: "Voice recording",
      did: "Recorded a short voice story about the watch.",
      understood: "Story about the watch; links to Dad, watch, photo, time.",
      changed: "Transcript saved. Links created. “I’ll remember that.”",
      next: "Return to Dad’s photographs — teaching is done."
    },
    {
      id: "06",
      src: "v2/media/06-return-dad.png",
      sec: 5,
      input: "Navigation · return",
      did: "Went back to Dad’s photos.",
      understood: "Exploration continues in the same set.",
      changed: "Same memories; archive is slightly richer.",
      next: "Another face in a photo needs a name."
    },
    {
      id: "07a",
      src: "v2/media/07a-who.png",
      sec: 7,
      input: "Rubber-band face + typing",
      did: "Selected a woman’s face; typed “Aunt Sue”.",
      understood: "This person is Aunt Sue.",
      changed: "Name attached to the face.",
      next: "MemoryBox asks who she was to the family."
    },
    {
      id: "07b",
      src: "v2/media/07b-sue-story.png",
      sec: 8,
      input: "Voice",
      did: "Recorded who Aunt Sue was to the family.",
      understood: "Relationship / story context for Sue.",
      changed: "Sue is teachable knowledge now.",
      next: "MemoryBox can find Sue across the archive."
    },
    {
      id: "08",
      src: "v2/media/08-sue-found.png",
      sec: 9,
      input: "Result · discovery",
      did: "Confirmed Sue.",
      understood: "Sue appears widely in the archive.",
      changed: "184 photos · 7 home movies · 3 stories — shown naturally.",
      next: "Open another photo — the watch may return."
    },
    {
      id: "09",
      src: "v2/media/09-story-available.png",
      sec: 7,
      input: "Click / select photo",
      did: "Opened another photograph with the same watch.",
      understood: "This object already has a story.",
      changed: "“Story Available” — prior teaching can play.",
      next: "Home — then a new question."
    },
    {
      id: "10",
      src: "v2/media/10-home.png",
      sec: 4,
      input: "Home",
      did: "Returned home.",
      understood: "Ready for a new exploration.",
      changed: "None required — continuity of place.",
      next: "Ask about Christmas from last year."
    },
    {
      id: "11",
      src: "v2/media/11-christmas.png",
      sec: 8,
      input: "Voice or typing",
      did: "Asked: “Show me Christmas from last year.”",
      understood: "Christmas · last year.",
      changed: "Christmas memories appear; dinner rolls are visible.",
      next: "Someone will ask about Dad’s roll recipe."
    },
    {
      id: "12",
      src: "v2/media/12-recipe.png",
      sec: 10,
      input: "Conversation + gathering",
      did: "Asked if Dad’s roll recipe still exists.",
      understood: "Recipe + related Christmas evidence.",
      changed: "Recipe card, photos, video, email, text, Grandpa’s voice — connected.",
      next: "The family decides to bake."
    },
    {
      id: "13",
      src: "v2/media/13-rolls.png",
      sec: 9,
      input: "Life happens · capture",
      did: "Made Grandpa’s rolls with the grandchildren.",
      understood: "A new family moment occurred today.",
      changed: "Quiet note: today the grandchildren made Grandpa’s rolls. Archive grows.",
      next: "Home again — exploration can continue."
    },
    {
      id: "14",
      src: "v2/media/14-alaska.png",
      sec: 8,
      input: "Typing",
      did: "Asked: “Show me our Alaska trip from 2026.”",
      understood: "A new trip / time to explore.",
      changed: "Alaska memories begin to open — the path continues.",
      next: "Indefinite exploration. Walkthrough ends; critique welcome."
    }
  ];

  const frame = document.getElementById("frame");
  const bar = document.getElementById("bar");
  const timer = document.getElementById("timer");
  const inputTag = document.getElementById("input-tag");
  const strip = document.getElementById("strip");
  const cDid = document.getElementById("c-did");
  const cUnd = document.getElementById("c-understood");
  const cCh = document.getElementById("c-changed");
  const cNext = document.getElementById("c-next");

  let i = 0;
  let playing = false;
  let t = null;

  scenes.forEach((s, idx) => {
    const b = document.createElement("button");
    b.type = "button";
    b.innerHTML = `<img src="${s.src}" alt="" /><span>${idx}. ${s.id}</span>`;
    b.addEventListener("click", () => { stop(); show(idx); });
    strip.appendChild(b);
  });

  function show(idx) {
    i = Math.max(0, Math.min(scenes.length - 1, idx));
    const s = scenes[i];
    frame.src = s.src;
    cDid.textContent = s.did;
    cUnd.textContent = s.understood;
    cCh.textContent = s.changed;
    cNext.textContent = s.next;
    inputTag.innerHTML = `Interaction shown: <strong>${s.input}</strong>`;
    timer.textContent = `Scene ${i} · ${s.sec}s`;
    bar.style.width = ((i / (scenes.length - 1)) * 100) + "%";
    [...strip.children].forEach((el, n) => el.classList.toggle("is-on", n === i));
  }

  function stop() {
    playing = false;
    if (t) { clearTimeout(t); t = null; }
  }

  function arm() {
    stop();
    playing = true;
    const s = scenes[i];
    t = setTimeout(() => {
      if (i < scenes.length - 1) {
        show(i + 1);
        arm();
      } else {
        playing = false;
        playBtn.textContent = "Play walkthrough";
        timer.textContent = "End — what do you wish it also did?";
      }
    }, s.sec * 1000);
  }

  const playBtn = document.getElementById("btn-play");
  document.getElementById("btn-play").addEventListener("click", () => {
    if (playing) { stop(); playBtn.textContent = "Play walkthrough"; return; }
    if (i >= scenes.length - 1) show(0);
    playBtn.textContent = "Playing…";
    arm();
  });
  document.getElementById("btn-pause").addEventListener("click", () => {
    stop();
    playBtn.textContent = "Play walkthrough";
  });
  document.getElementById("btn-prev").addEventListener("click", () => { stop(); show(i - 1); });
  document.getElementById("btn-next").addEventListener("click", () => { stop(); show(i + 1); });

  show(0);
})();

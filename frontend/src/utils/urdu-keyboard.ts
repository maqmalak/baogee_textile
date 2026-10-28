/**
 * Phonetic Urdu keyboard for Urdu fields (every form field whose name ends in `urdu_name`, or any input with
 * `data-urdu`): an English keyboard types Urdu, letter by sound — a→ا b→ب p→پ t→ت, Shift for the extra letters
 * (T→ٹ D→ڈ R→ڑ N→ں …). Close to the common CRULP phonetic layout. Only Latin keys are converted, so a real Urdu
 * keyboard (Windows / Android Urdu) keeps working; digits and spaces pass through.
 */
const MAP: Record<string, string> = {
  a: "ا", b: "ب", c: "چ", d: "د", e: "ع", f: "ف", g: "گ", h: "ہ", i: "ی", j: "ج", k: "ک", l: "ل", m: "م",
  n: "ن", o: "ہ", p: "پ", q: "ق", r: "ر", s: "س", t: "ت", u: "ء", v: "ط", w: "و", x: "ش", y: "ے", z: "ز",
  A: "آ", B: "ب", C: "ث", D: "ڈ", E: "ٰ", F: "ف", G: "غ", H: "ح", I: "ِ", J: "ض", K: "خ", L: "ل", M: "م",
  N: "ں", O: "ۃ", P: "ُ", Q: "ق", R: "ڑ", S: "ص", T: "ٹ", U: "ئ", V: "ظ", W: "ؤ", X: "ژ", Y: "َ", Z: "ذ",
  ",": "،", ".": "۔", "?": "؟", ";": "؛", "`": "ھ", "~": "ً",
};

/** Keys and their Urdu letters, for the on-screen hint. */
export const URDU_KEY_HINT = "a ا · b ب · p پ · t ت · T ٹ · s س · j ج · c چ · H ح · K خ · d د · D ڈ · z ز · r ر · R ڑ · x ش · S ص · g گ · l ل · m م · n ن · N ں · w و · h ہ · ` ھ · i ی · y ے";

const isUrduInput = (el: EventTarget | null): el is HTMLInputElement | HTMLTextAreaElement =>
  (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) &&
  (el.dataset.urdu !== undefined || Boolean(el.closest('[data-field$="urdu_name"]')));

function insert(el: HTMLInputElement | HTMLTextAreaElement, text: string) {
  // insertText goes through the browser's editing pipeline: React sees a normal input event and Ctrl+Z still works.
  if (document.execCommand?.("insertText", false, text)) return;
  const start = el.selectionStart ?? el.value.length, end = el.selectionEnd ?? start;
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value")?.set;
  setter?.call(el, el.value.slice(0, start) + text + el.value.slice(end));
  el.setSelectionRange(start + text.length, start + text.length);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

let installed = false;

/** Install once (main.tsx): one document-level key listener serves every Urdu field, including ones added later. */
export function installUrduKeyboard() {
  if (installed || typeof document === "undefined") return;
  installed = true;
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing || !isUrduInput(e.target)) return;
    const urdu = MAP[e.key];
    if (!urdu) return;
    e.preventDefault();
    insert(e.target, urdu);
  }, true);
}

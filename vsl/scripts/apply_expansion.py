"""
vsl/scripts/apply_expansion.py
Apply the v2 script expansion to segments.json:
  - Replace `spoken` for expanded segments with the longer v2 content
  - Re-compute each segment's hash (so heygen_render.py re-renders)
  - Inject SSML <break> tags between sentences for natural pacing
  - Optionally seed .env with HEYGEN_VOICE_SPEED=0.85

Run after parse_script.py — this overwrites segments.json's spoken field with
the v2 text. Re-running parse_script.py would revert it (we keep the docx as
the canonical reference but ship the v2 spoken text as the active version).
"""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEGMENTS_FILE = ROOT / "segments.json"

# Sentence break tag — HeyGen SSML
BREAK_SENT = '<break time="0.4s"/>'
BREAK_PARA = '<break time="0.8s"/>'
BREAK_STEP = '<break time="0.5s"/>'

# v2 SPOKEN TEXT — exact lines that go to HeyGen
EXPANSIONS: dict[str, str] = {
    # NB: leave hook/objection/proof/gap/outro untouched (they're already tight)

    "soft_cta": (
        "I work with founders — people running real businesses who know they should "
        "be visible online, but can't stand being on camera every day. Maybe you're "
        "an agency owner who closes five-figure deals on calls, but never shows your "
        "face. Maybe you run a SaaS, a coaching practice, a consultancy. You know if "
        "more people saw you, more people would buy. But the camera is in the way.\n\n"
        "That's exactly what we do at ZeroHands. If that's you, there's a link below "
        "to book a call — we'll look at your business and see if we're a fit. But "
        "first, stay with me — because by the end of this video, you'll have the "
        "exact system to do this yourself."
    ),

    "pain": (
        "Let's be honest about where most founders are right now. You know visibility "
        "drives revenue. You know if people don't see you, they don't buy from you. "
        "You know content is the cheapest way to grow your business today.\n\n"
        "But here's what actually happens. You're busy — running the business, "
        "handling clients, managing a team, dealing with life. And on top of all "
        "that, you're supposed to film, edit, and post content every single day? "
        "That's not sustainable.\n\n"
        "So you do what most founders do. You record one video when you're feeling "
        "motivated, on a Sunday afternoon. You post it. Engagement is okay. Then "
        "nothing for three weeks. The algorithm forgets who you are. Your "
        "competitors stay consistent. And every week you stay quiet, you're paying "
        "for it — in DMs you never get, calls you never book, customers who go "
        "somewhere else.\n\n"
        "And maybe you're just not a camera person. Setting up the lights, getting "
        "ready, doing ten takes, hating how you look — and then never posting it "
        "anyway.\n\n"
        "So you stay invisible. And the founders who are visible? They take your "
        "customers.\n\n"
        "The real problem isn't you. The content game is built to burn founders "
        "out. Something has to change."
    ),

    "solution": (
        "That's where the AI avatar system comes in. The whole idea is simple — "
        "scale your presence without scaling your effort.\n\n"
        "You build a digital version of yourself that looks like you, sounds like "
        "you, and speaks like you. You record yourself once, and it creates content "
        "forever.\n\n"
        "There are three pieces. One — you clone your face, so your audience sees a "
        "person, not a stock photo. Two — you clone your voice, so what they hear is "
        "unmistakably yours, not robotic AI. Three — you clone your expertise, so "
        "the words sound like you actually wrote them, in your tone, with your "
        "stories.\n\n"
        "Put those together and you get unlimited content, in your face and your "
        "voice, without you ever touching a camera again. Same person on the "
        "screen. Same words you would have said. The only difference — you didn't "
        "have to be there to record it."
    ),

    "value_step1_strategy": (
        "So how does this actually work? Three steps. Strategy, cloning, execution. "
        "Let me give you the whole thing.\n\n"
        "Step one is content strategy. This is the part most people skip — and it's "
        "why their content goes nowhere. Avatar or no avatar, if the message is "
        "generic, nobody cares.\n\n"
        "Before any avatar, you need three things. First, your niche — exactly who "
        "you help and what problem you solve. Not \"I help businesses grow\" — "
        "that's invisible. Try \"I help DTC founders scale to a million in revenue "
        "without ads.\" That's a niche.\n\n"
        "Second, your content pillars — the three core themes you talk about again "
        "and again. Pick three, write them down, never drift. If you're a fitness "
        "coach, maybe it's body recomposition, mindset, and client wins. Three "
        "lanes. Every video lives in one of them.\n\n"
        "Third, your content types. There are three types, and you need all three. "
        "Virality content — broad, relatable stuff that gets you discovered by "
        "strangers. Authority content — specific, useful stuff that makes a "
        "follower trust you. And conversion content — direct content that turns "
        "trust into a booked call.\n\n"
        "And every single video, no matter the type, follows the same structure. A "
        "hook in the first three seconds. A body that delivers one idea clearly. A "
        "clear call to action at the end. Hook, body, CTA. Every time. Get that "
        "structure right and your content starts pulling its weight."
    ),

    "value_step2_clone": (
        "Step two is building the clone. Three tools.\n\n"
        "For your face, you use HeyGen. You record two to five minutes of yourself "
        "once — looking dead at the camera, no edits, no movement, no fidgeting. "
        "You upload that footage, and HeyGen builds a video clone of you that can "
        "be re-purposed for any script you throw at it. The key is the source "
        "footage: shoot it in good light, with the same wardrobe you'd actually "
        "wear, against a real background, not a green screen.\n\n"
        "For your voice, you use ElevenLabs. You record about an hour of clean "
        "audio. Not robotic narration — talk like you're explaining your business "
        "to a friend over coffee. ElevenLabs takes that hour and clones your voice "
        "so well it carries your tone, your warmth, your pacing, even your filler "
        "words. Connect the clone to HeyGen and now every avatar video uses your "
        "real voice.\n\n"
        "And for the words, you use Claude to write scripts that sound like you. "
        "Feed Claude five of your real captions or transcripts, and it learns your "
        "phrasing. Now you have a writer that never goes off-brand.\n\n"
        "Let me quickly show you the face and voice part live.\n\n"
        "That's it. Once it's set up, you write a script, pick your look, hit "
        "generate — and you've got a video in your face and voice in ten minutes."
    ),

    "value_step3_funnel": (
        "Step three is where the money is — and where most people stop too early.\n\n"
        "Because here's the thing nobody tells you. You can have the best avatar "
        "and the best content, post every single day for six months — but if "
        "there's no system to capture and convert the people watching, you just "
        "get views. Not clients.\n\n"
        "So you build a funnel. It works like this. Someone comments a specific "
        "keyword on one of your posts — say, BLUEPRINT or GUIDE. ManyChat sees "
        "that comment automatically, sends them a DM, captures their email and "
        "phone number, and delivers a piece of free value — usually a PDF or a "
        "short video.\n\n"
        "Then behind ManyChat, you have n8n and an AI agent that does the "
        "qualifying. The agent reads what the lead said, scores them on three "
        "criteria — are they a real business owner, do they have budget, do they "
        "have urgency. The unqualified leads get a polite nurture sequence. The "
        "qualified ones get a booking link with your real Calendly schedule.\n\n"
        "By the time they hit your calendar, they've been pre-screened. You only "
        "ever talk to serious people. No tire-kickers. No twenty-minute calls with "
        "someone who was never going to buy.\n\n"
        "Your avatar makes the content. The funnel catches the leads. The agent "
        "does the qualifying. You just show up to the calls."
    ),

    "why_it_works": (
        "Why does this whole system work? Five reasons.\n\n"
        "It removes the burnout of posting — you go from \"I should film today\" "
        "to \"I already shipped this week's content.\"\n\n"
        "It removes the fear of being on camera — your avatar shows up, you don't "
        "have to.\n\n"
        "It saves you hours every single week — what used to be a full Saturday is "
        "now twenty minutes on Monday.\n\n"
        "It gives you consistent visibility — five posts a week, every week, no "
        "skipped days, no algorithm penalty.\n\n"
        "And it scales — without you sacrificing your time, your energy, or your "
        "life outside work.\n\n"
        "This isn't about replacing you. It's about removing the busy work, so you "
        "can do what only you can do — run your business and close deals."
    ),

    "offer": (
        "At ZeroHands, we build the whole thing for you.\n\n"
        "We start by researching the best looks and formats for your brand — not "
        "generic templates, but a creative direction built around how your "
        "customers want to see you. Then we arrange the shoot, so you record once "
        "— properly, with our team, in your wardrobe — and never have to be on "
        "camera again.\n\n"
        "We build your avatar. We clone your voice. We build your funnel — "
        "ManyChat, n8n, and the qualifying agent — so it actually generates booked "
        "calls, not just views.\n\n"
        "Then, every single week — we do the trend research, write the scripts in "
        "your voice, generate the videos, edit them, schedule them, and post them "
        "for you. All you do is approve the script. That's it. Your content ships "
        "every week, and your calendar fills with qualified calls — while you "
        "focus on the business."
    ),

    "risk_cta": (
        "Look — I spent seventeen years in engineering before I built this. I "
        "don't do hype. If we get on a call and it's not a fit, I'll tell you "
        "straight to your face. No pressure, no follow-up sequence trying to wear "
        "you down.\n\n"
        "So here's the next step. Click the link below and book a call. It's a "
        "no-pressure consultation — we'll look at your business, your numbers, "
        "your current content situation, and if it makes sense, we'll show you "
        "exactly how we'd plug this in for you.\n\n"
        "If you're a founder who knows you need to be visible, but you're done "
        "burning out trying to do it yourself — this is for you. Book the call. "
        "Let's see if we're a fit."
    ),

    # Outro — strip the docx footer ("Voice-clone tip:" + "ZeroHands |") that the parser
    # was inadvertently including in the spoken text. Keep just the actual outro line.
    "outro": (
        "And if this video was valuable, do me a favor — like it, subscribe, and "
        "comment what you want me to break down next. I'll see you in the next one."
    ),
}


SENTENCE_END_RE = re.compile(r"(?<=[.?!])\s+")


def inject_breaks(text: str) -> str:
    """Insert SSML <break> tags between sentences and at paragraph boundaries.

    Paragraph break (double-newline) becomes BREAK_PARA.
    Sentence break (period/question/exclamation + whitespace) becomes BREAK_SENT.
    'Step one is...' style transitions become BREAK_STEP.
    """
    # Paragraph-level
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    out = []
    for para in paragraphs:
        # Sentence-level
        para = SENTENCE_END_RE.sub(f" {BREAK_SENT} ", para)
        # Add a sentence break after the last sentence too (so the paragraph break has a clean attach point)
        if not para.endswith(BREAK_SENT):
            para = para + " " + BREAK_SENT
        # Step heading emphasis
        para = re.sub(r"\b(Step (?:one|two|three) is)\b", rf"\1 {BREAK_STEP}", para, flags=re.I)
        out.append(para)
    return f" {BREAK_PARA} ".join(out)


def _hash(text: str, look: str) -> str:
    h = hashlib.sha256(); h.update(text.encode()); h.update(b"|"); h.update(look.encode())
    return h.hexdigest()[:12]


def main() -> int:
    if not SEGMENTS_FILE.exists():
        print("missing segments.json — run parse_script.py first", file=sys.stderr)
        return 1
    segments = json.loads(SEGMENTS_FILE.read_text())
    changed = 0
    for seg in segments:
        sid = seg["id"]
        if sid in EXPANSIONS:
            new_text = EXPANSIONS[sid].strip()
            with_breaks = inject_breaks(new_text)
            seg["spoken"] = with_breaks
            seg["hash"] = _hash(with_breaks, seg["look"])
            changed += 1
    SEGMENTS_FILE.write_text(json.dumps(segments, indent=2, ensure_ascii=False))
    total_words = sum(len(re.sub(r"<[^>]+>", "", s["spoken"]).split()) for s in segments)
    print(f"Updated {changed} segments → segments.json")
    print(f"Total spoken word count (SSML stripped): {total_words}")
    print("Per-segment expanded counts:")
    for s in segments:
        if s["id"] in EXPANSIONS:
            wc = len(re.sub(r"<[^>]+>", "", s["spoken"]).split())
            print(f"  {s['id']:25s} {wc:4d} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())

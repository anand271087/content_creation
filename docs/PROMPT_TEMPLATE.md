# Client Prompt Template

This is where your scripting prompt goes. The pipeline uses whatever you paste
in the block below to drive Stage 1 — the script generator. Everything else in
the pipeline (avatar, b-roll, audio, composition, captions, social copy) runs
automatically downstream of the script the prompt produces.

You own this file. We don't.

---

## How It Works (One Paragraph)

You write a prompt that tells the language model how to turn a topic or content
brief into a structured 10-section script. The pipeline injects your prompt
into the model call along with the input topic, captures the model's response,
parses it as JSON, validates it against the schema, and hands it off to every
downstream stage. If the prompt produces a valid script, the pipeline runs
end-to-end. If it doesn't, the pipeline reports the schema violation and you
adjust the prompt.

---

## The Required Output Schema

Whatever you write in your prompt, the model must return JSON matching this
shape. Anything else gets rejected by the contract validator.

```json
{
  "title":               "<60 chars max — used for thumbnail + title bar>",
  "total_duration_sec":  <number — target reel length, 60 to 95>,
  "bgm_transition_sec":  <number — when ambient music shifts from tension to warm>,
  "bgm_dip_timestamps":  [<3 numbers — trigger moment timestamps in seconds>],
  "full_spoken_script":  "<the complete narration the avatar will speak>",
  "grand_takeaway_line": "<one quotable line — used in the takeaway template>",
  "tool_mentioned":      "<the product, framework, or methodology name>",
  "sections": [
    {
      "id":             "<one of: hook, context, trigger_1, body_1,
                          trigger_2, body_2, trigger_3, bridge,
                          grand_takeaway, emotion_save>",
      "label":          "<human-readable section label>",
      "start_sec":      <number>,
      "end_sec":        <number>,
      "spoken":         "<the words the avatar says in this section>",
      "on_screen_text": ["<3-5 short uppercase phrases>"],
      "broll_prompt":   "<one-sentence visual description for motion graphics>",
      "expression_cue": "<how the avatar should look>",
      "vocal_direction":"<how the avatar should sound>",
      "bgm_dip":        <boolean — true for trigger sections>,
      "bgm_track":      <1 or 2>,
      "bgm_transition_here": <boolean — true on grand_takeaway only>,
      "broll_type":     "<one of: clip, screen, diagram, terminal>"
    }
    // ... 9 more section objects
  ]
}
```

The pipeline expects exactly 10 sections with the IDs listed above. Re-ordering,
renaming, or skipping IDs breaks the downstream stages.

---

## ▶ Your Prompt Goes Here

Paste your scripting prompt into the block below. Keep the surrounding fences
exactly as shown — the pipeline reads the block between them.

<!-- BEGIN_CLIENT_PROMPT -->
```
[Your scripting prompt here.]

[Tell the model who it is writing for, what tone to use, what topics are in
scope, what the brand voice sounds like, what hooks resonate with your
audience, what calls-to-action you want, and what to avoid.]

[Tell it to return only the JSON object — no commentary, no markdown fences,
no explanation. The pipeline parses the raw JSON.]

[Tell it the target reel duration (60 to 90 seconds), the spoken word budget
(~180 to 220 words), and the line-by-line constraints for each section.]

[Specify your input variables — typically a topic line or a content brief.
Reference them using {{topic}} or {{brief}} placeholders that the orchestrator
will substitute at runtime.]
```
<!-- END_CLIENT_PROMPT -->

---

## Input Variables

The orchestrator substitutes these placeholders into your prompt at runtime:

| Placeholder      | Substituted with                                       |
|------------------|--------------------------------------------------------|
| `{{topic}}`      | The topic string passed via `--topic` on the command line |
| `{{transcript}}` | The contents of the file passed via `--transcript`        |
| `{{audience}}`   | The audience profile from `.env` (optional)               |
| `{{tone}}`       | The tone profile from `.env` (optional)                   |

You can ignore any placeholder you don't need.

---

## Worked Example (Reference Only — Replace With Your Own)

This is a reference shape only. Replace it with your own prompt before running
the pipeline.

<!-- BEGIN_REFERENCE_EXAMPLE -->
```
You are a senior B2B content strategist. You write short-form vertical video
scripts for procurement and supply-chain leaders.

INPUT
{{topic}}

YOUR TASK
Produce a 75-second reel script as a single JSON object. The structure follows
a 10-section narrative arc — hook, context, three triggers interleaved with
two body sections, a bridge, a grand takeaway, and a closing emotion+save CTA.

NON-NEGOTIABLE RULES
- Opening 5 seconds is a pattern interrupt — a number, a question, a
  contrarian claim. Never a greeting.
- Each section's spoken text fits inside its time budget at 150 words per
  minute.
- No filler. No "in this video" intros. No sign-offs unless they are part of
  the CTA.
- One clear takeaway. One clear next action.
- Active voice. Eighth-grade readability.
- Cite a specific number, name, or example in at least two sections.
- Use {{tone}} as the voice. Default to "confident, direct, advisory".

RETURN
Return only the JSON object. No prose around it.
```
<!-- END_REFERENCE_EXAMPLE -->

---

## Running The Pipeline With Your Prompt

Once your prompt is pasted into the block above, run the pipeline normally:

```bash
python3 pipeline.py --topic "<your topic line>"
```

The pipeline reads your prompt from this file, substitutes the input
variables, calls the model, parses the response, and proceeds through every
downstream stage automatically.

---

## Troubleshooting

| Symptom                                              | Likely Cause                              | Fix                                        |
|------------------------------------------------------|--------------------------------------------|---------------------------------------------|
| `Schema validation failed: missing field "X"`        | Prompt doesn't enforce all required keys   | Add the missing field to your output spec   |
| `Script over 95 seconds — rejected by gate`          | Spoken word count too high                 | Tell the model to cap at 220 words          |
| `Section IDs don't match expected set`               | Prompt allows alternative IDs              | Pin the IDs explicitly in the prompt        |
| `Model returned markdown fences around JSON`         | Prompt didn't forbid them                  | Add "Return raw JSON, no fences" to prompt  |
| `Tool name is empty`                                 | Prompt didn't ask for `tool_mentioned`     | Add an explicit instruction for the field   |

---

## Versioning Your Prompt

We recommend keeping this file under version control. Every meaningful change
to the prompt is a content strategy change — track it like code.

```bash
git add docs/PROMPT_TEMPLATE.md
git commit -m "Tighten hook constraints in client prompt"
```

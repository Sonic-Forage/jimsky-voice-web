# GPT Image stack (the "flare" path)

How JIMSKY makes and edits images. **`gpt-image-2.5-flare`** is the workhorse for both
text-to-image and image-to-image editing; it is reached through the Comfy Cloud workflow node
`OpenAIGPTImageNodeV2`.

## The one thing that trips everyone up

**Paid partner nodes cannot be driven over the plain REST API.** `POST /api/prompt` with the
workspace API key returns:

    Unauthorized: Please login first to use this node.

The Comfy Cloud MCP server uses **OAuth**, not that key, so the flare path must go through MCP
(`submit_workflow`). A standalone script can do everything else - upload inputs, download
outputs, publish to the stage - but the submit itself belongs to whatever holds the OAuth
session (the Hermes MCP tools, or a human in the Comfy Cloud UI).

## Text to image

```json
{
  "2": {"class_type": "OpenAIGPTImageNodeV2", "inputs": {
      "prompt": "…",
      "model": "gpt-image-2.5-flare",
      "model.size": "1024x1024",
      "model.quality": "high",
      "model.background": "opaque",
      "model.custom_width": 1024,
      "model.custom_height": 1024,
      "n": 1}},
  "3": {"class_type": "SaveImage", "inputs": {
      "filename_prefix": "jimsky_t2i", "images": ["2", 0]}}
}
```

## Image to image (edit)

Add a `LoadImage` and point `model.images.image_1` at it. Upload the source first
(`POST /api/upload/image`, field `image`, `type=input`) and use the returned `name`.

```json
{
  "1": {"class_type": "LoadImage", "inputs": {"image": "<uploaded name>"}},
  "2": {"class_type": "OpenAIGPTImageNodeV2", "inputs": {
      "model": "gpt-image-2.5-flare",
      "model.size": "1024x1536",
      "model.quality": "high",
      "model.background": "opaque",
      "model.custom_width": 1024,
      "model.custom_height": 1024,
      "model.images.image_1": ["1", 0],
      "n": 1,
      "seed": 8814,
      "prompt": "Edit this image. Keep the subject, pose and framing exactly as they are. …"}},
  "3": {"class_type": "SaveImage", "inputs": {
      "filename_prefix": "jimsky_edit", "images": ["2", 0]}}
}
```

### Rules the node enforces

- `model.custom_width`, `model.custom_height` and `model.background` are **required even when
  inert** — omit them and the job fails validation.
- Keep the edit instruction explicit about preservation ("keep the subject, pose and framing"),
  otherwise the model reinterprets the whole scene instead of editing it.
- Always end image prompts with `No text, no lettering, no watermark, no signature.` The model
  will otherwise invent signage text.
- The bundled node index can lag the cloud and warn that `gpt-image-2.5-flare` is unknown. That
  is advisory; the cloud is the authoritative validator. Confirm by reading the reported
  pixel size off the output rather than trusting the requested size.

## Getting the result

- `GET /api/jobs/<prompt_id>` reports status and the output filename.
- `GET /api/view?filename=<name>&type=output` **302s** to the file — use `curl -L`, or you will
  save a zero-byte file and publish an empty "image".

## Publishing to the stage

    JIMSKY_MEDIA_BASE=https://jimsky-media.<ip>.nip.io \\
      python3 publish-media.py out.png --caption "EDIT · what changed" --kind image

The front end picks it up within ~4 seconds. Video and audio work the same way.

## In the voice flow

Ask JIMSKY for an image and it goes: **MCP `submit_workflow`** (flare node) → poll
`/api/jobs/<id>` → download with `-L` → `publish-media.py` → the stage. Hermes already has the
comfy-cloud MCP server configured, which is why the voice agent can do this without any new
API plumbing.

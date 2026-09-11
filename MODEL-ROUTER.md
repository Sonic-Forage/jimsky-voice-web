# The model router

One agent, many brains. The studio is not loyal to a single model: the router knows which models we can
reach, what each is for, and it can run one prompt through several of them at once and report what
actually came back.

    GET  /api/router/models          what is reachable, with prices and their source
    POST /api/router/compare         {prompt, models[], max_tokens} → measured results

Both are behind the same `X-HUD-Key` gate as everything else on the HUD backend, because these calls
spend money.

## What is reachable

| Tier | Models | Note |
|---|---|---|
| Frontier | GPT-5.6 luna · sol · GPT-5.5 · DeepSeek V4 Pro | luna is the voice agent's own backend, so the router and the room agree |
| Fast + cheap | DeepSeek Flash · GLM 5.3 Flash · Qwen 3.8 Flash | DeepSeek Flash is Hermes' default brain; most calls should land here |
| Open weights | Qwen 3.8 Max · DeepSeek V4 Flash Vision · GLM Flash | no vendor lock; the honest test of whether closed models are still needed |
| Free tier | 22 OpenRouter models listed at $0/token | testing costs nothing |
| Self-hosted | 3 RunPod Ollama endpoints | **all answering 403 — pods down.** Private inference is a pod restart away |

## Rules the implementation follows

1. **Nothing is estimated.** Latency is the wall clock around the call; token counts come from the
   provider's own `usage` block.
2. **Cost is only reported when a price is published**, and the source of that price is returned with
   it (`price_source`). Where DeepSeek does not publish per-token pricing in our source, the card reads
   *unpublished* rather than guessing a number.
3. **A truncated answer is flagged**, not silently presented as a complete one (`truncated`).
4. **A reasoning trace is not an answer.** Some models spend the entire output budget on hidden
   reasoning and return no visible text. The router detects that, returns the reasoning anyway, and
   marks it `from_reasoning` so the UI can warn instead of pretending it was the answer.
5. **Errors are data, not exceptions.** A failed model returns `ok: false` with its error, so one dead
   provider does not blank a four-way comparison.

## Measured findings

Same prompt, three models, run in parallel through the deployed front end:

| Model | Latency | Tokens | Cost | Note |
|---|---|---|---|---|
| GPT-5.6 luna | 2,155 ms | 28→86 | $0.000109 | fastest + cheapest |
| DeepSeek Flash | 4,891 ms | 52→900 | unpublished | hit the output cap inside its reasoning — no visible answer returned |
| Qwen 3.8 Max (open weights) | 10,714 ms | 84→393 | $0.002526 | 5.0× slower and 23× the cost of luna on this prompt |

Three things worth keeping:

- **Luna is both fast and cheap here.** The frontier model is not the expensive option on short prompts.
- **Open weights are a freedom move, not automatically a savings move.** Going open bought us no money
  on this task; it buys us no vendor in the path, which is a different and valid reason.
- **DeepSeek Flash burned 900 tokens thinking and returned nothing visible.** That is a real
  characteristic of reasoning models with a token cap, and it is exactly why the flag exists.

## Using it from the UI

The **MODELS** tab: pick up to four brains (a card highlights when selected), type one prompt, hit
RUN COMPARISON. Every answer panel shows its own latency, token counts, cost and the source of that
price, and the verdict line under the results states fastest and cheapest **as measured in that run** —
it is computed from the response, not written into the copy.

## Honest gaps

- Self-hosted open weights are offline (403). One pod brings them back.
- DeepSeek pricing is not in our price source, so any multi-model total that includes it is a floor.
- The router measures one turn at a time. It does not yet route automatically by task type — that
  selection is currently a human choice in the UI.

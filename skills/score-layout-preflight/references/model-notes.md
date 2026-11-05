# Initial model choice — checked 2026-11-05

Start an evaluation with GPT-5.4 mini (`gpt-5.4-mini`; documented snapshot `gpt-5.4-mini-2026-03-17`). It supports image input and structured outputs. Standard pricing on its model page is USD $0.75 per million input tokens and $4.50 per million output tokens. This is a cost-conscious candidate, not a measured guarantee of music-layout accuracy. Skill installation does not select this model or connect the app to the API.

Illustrative budget: 5,000 total billed input tokens (including the image) and 1,000 total billed output tokens cost $0.00825 per page; 14 similar pages would cost $0.1155. This is arithmetic under assumed token usage, not an image-token estimate or quote. Actual image dimensions/detail, output length, reasoning tokens and retries change the cost. Record API usage and cap retries. Recheck prices before deployment.

Start with one page image and concise JSON. Increase detail or inspect a system crop when lines are ambiguous. Avoid uploading the full score repeatedly. Use deterministic geometry checks and a visual correction overlay; precise spatial localization is a documented vision limitation. Benchmark on varied choir pages before deciding whether a stronger model is needed for failures.

Sources:
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
- https://developers.openai.com/api/docs/guides/images-vision

Fine-tuning the recognition backend is separate work. This model's documentation currently marks fine-tuning unsupported. Do not describe prompt/skill changes as training.

#### thakkarparth007.github.io

#### Citation (APA): thakkarparth007.github.io. (2023). copilot-explorer [Programming, MachineLearning, GPT] [Kindle Android version]. Retrieved from Amazon.com

#KindleExport
#Programming
#MachineLearning
#GPT


- Created: 2023-01-27_23-20-47

---

### copilot-explorer [Programming, MachineLearning, GPT]
- There are two main components of Github Copilot: Client: The VSCode extension collects whatever you type (called prompt), and sends it to a Codex –like model. Whatever the model returns, it then displays in your editor. Model: The Codex-like model takes the prompt and returns suggestions that complete the prompt. Secret Sauce 1: Prompt engineering
- The extension encodes a bunch of information about your project in the prompt.
- prompt includes both a prefix and a suffix. Copilot will then send this prompt (after some formatting) to the model. In this case, Copilot is invoking Codex in “insert mode” aka fill-in-middle (FIM) mode, because suffix is non-empty.
- Secret Sauce 2: Model Invocation
- Inline/ GhostText Main module Here, the extension asks for very few suggestions (1– 3) from the model in order to be fast. It also aggressively caches results from the model. Furthermore, it takes care of adapting the suggestions if the user continues typing. It also takes care of debouncing the model requests if the user is typing fast. This UI also has some logic to prevent sending requests in some cases. For example , if the user is in the middle of a line , then the request is only sent if the characters to the right of the cursor are whitespace, closing braces etc.
- More interestingly, after generating the prompt, this module checks if the prompt is “good enough” to bother with invoking the model. It does this by computing what is called “contextual filter score” . This score seems to be based on a simple logistic regression model over 11 features such as the language, whether previous suggestion was accepted/ rejected, duration between previous accept/ reject, length of last line in the prompt, last character before cursor, etc.
- Copilot Panel Main module , Core logic 1 , Core logic 2 . This UI requests more samples (10 by default) from the model than the inline UI. This UI doesn’t appear to have contextual filter logic (makes sense, if the user explicitly invoked this, you don’t want to not prompt the model).
- Before a suggestion is shown (via either UI), Copilot performs two checks: If the output is repeatitive (e.g., foo = foo = foo = foo...), which is a common failure mode of language models, then the suggestion is discarded . This can also happen at the Copilot proxy server or client or both. If the user has already typed the suggestion, then it is discarded. Secret Sauce 3: Telemetry
- open-source FauxPilot
- Measuring Copilot’s success rate isn’t just a matter of trivially computing the number of accepts/ number of rejects. That’s because people typically accept and then make some modifications. As a result, Github folks check if the suggestion that was accepted is still present in the code. This gets done at different time lengths after the insertion. Specifically, after 15s, 30s , 2min , 5min and 10min timeouts , the extension measures if the accepted suggestion is “still in code”.
- they measure edit distance ( at character level and word level) between the suggested text, and a window around the insertion point. Then, if the ‘word’ level edit distance between inserted and the window is less than 50% (normalized to suggestion size), then the suggestion is considered “still in code”

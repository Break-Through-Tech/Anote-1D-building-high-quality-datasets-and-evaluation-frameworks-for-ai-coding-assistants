Hi Natan,

Thank you for submitting such an exceptional and forward-thinking challenge project for our Fall 2026 AI Studio. Building robust evaluation frameworks for coding assistants using the harbor-framework/terminal-bench data is an excellent, high-impact initiative that perfectly aligns with our curriculum goals.
To make sure our Machine Learning Foundations fellows make consistent progress without running into the resource limitations or timeout restrictions of Google Colab's free tier, I want to suggest a few practical scoping guardrails for the starter milestones:

1. **Focusing on Advanced Prompting/RAG over Weight Tuning:** Since supervised fine-tuning (SFT) can quickly bottleneck on basic Colab environments, let's have the students focus October's modeling milestone on creating highly optimized Few-Shot Prompt Engineering pipelines and lightweight context routing models utilizing your API keys. This achieves the accuracy boosts you're looking for while keeping execution stable.

2. **Isolating a Single Code Domain:** To keep dataset parsing clean and highly predictable in September , let’s restrict the scope to a single programming language or a targeted functional track within terminal-bench (for example, generating Python unit tests specifically).

3. **Standardizing Evaluation Benchmarks:** Dynamically executing live code inside Colab sandboxes to calculate a broad $Pass@k$ loop can be tricky for foundation students. I recommend we tightly lock the evaluation down to a fixed, static metric—specifically focusing on a strict $Pass@1$ standard or tracking deterministic structural correctness and semantic similarity scores via standard NLP evaluation libraries.

These specific bounds will protect the student teams from complex infrastructure headaches, letting them spend 100% of their energy delivering clean, high-fidelity datasets and benchmarking workflows that directly benefit Anote.

Let me know if you are open to adjusting the starter requirements to match these guardrails. Looking forward to partnering with you as a Challenge Advisor this fall!

Thanks,
Dr. Uohna 

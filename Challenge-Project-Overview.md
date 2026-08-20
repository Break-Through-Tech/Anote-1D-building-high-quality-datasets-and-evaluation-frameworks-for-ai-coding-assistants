
# Building High-Quality Datasets and Evaluation Frameworks for AI Coding Assistants


**Company / Org:** Anote  
**Challenge Advisor:** Natan Vidra, nvidra@anote.ai.  
**AI Studio Coach:** Bhavya Gopal, bhavya.gopal@breakthroughtech.ai.  
**Program:** Break Through Tech AI Studio - Fall 2026

---

## 🏢 About Anote

Anote is focused on enhancing developer productivity through innovative AI solutions in the tech industry. Our solutions harness the power of AI to support coding, debugging, and understanding code, aiming to transform the developer experience and improve software quality.

---

## 🎯 The Challenge

### Project Summary
In this project, you will use code datasets, developer interactions, and code evaluation benchmarks alongside large language models (LLMs) and prompt-based evaluation techniques to build and evaluate an AI system that improves code generation, debugging, and code understanding performance. This will help our company address the challenge of improving accuracy, reliability, and evaluation of AI-powered coding assistants in real-world development environments.

Scoping note (per SME review): To keep the project stable on Google Colab's free tier, this project is scoped around prompt engineering and retrieval rather than model fine-tuning, and around static evaluation rather than live sandboxed code execution. See the guardrails below

### Success Criteria
_Quantitative Metrics:

Pass@1 (does the top generated candidate pass a fixed, pre-defined test case set — evaluated statically rather than through a live execution loop)
Structural / semantic correctness scoring via standard NLP similarity metrics (e.g., CodeBLEU, exact-match, AST-diff)
Accuracy of bug fixes / code transformations against reference solutions
Reduction in error rate vs. baseline model outputs

_Qualitative Metrics:_
- Code readability and quality
- Developer usefulness (does output solve the task effectively)

_Final Outcome (December):_
- A working evaluation framework for AI coding models
- A curated dataset for code tasks (generation, fixing, testing)
- Demonstrated improvement vs baseline models
- A reproducible pipeline for benchmarking coding assistants

### Stretch Goals
- Build a real-time evaluation system integrated into the Anote coding assistant
- Add reinforcement learning / feedback loops (RLHF or RLAIF)
- Expand to multi-file or full-repo reasoning
- Add code execution environments (sandbox testing)
- Create a leaderboard comparing models (Claude, GPT, open-source)
- Incorporate human-in-the-loop feedback pipelines (core to Anote’s approach

### Project Milestones

Use these milestones to guide your work. Your team will create a **GitHub Projects board** to track tasks within each milestone.

| Month | Milestone | Key Activities |
|---|---|---|
| September | Foundations & Data | • Define project scope (e.g., code generation, bug fixing, or code explanation)<br>• Curate or construct a dataset:<br>&nbsp;&nbsp;&nbsp;&nbsp;◦ Code snippets + prompts (e.g., "fix this function," "generate unit tests")<br>&nbsp;&nbsp;&nbsp;&nbsp;◦ Ground truth outputs (correct code / expected behavior)<br>• Perform data preprocessing and formatting<br>• Establish baseline models (e.g., GPT/Claude or open-source LLMs)<br>• Define evaluation metrics (accuracy, pass@k, etc.) |
| October | Modeling & Evaluation | • Fine-tune or adapt models on curated datasets (if feasible)<br>• Build evaluation pipelines:<br>&nbsp;&nbsp;&nbsp;&nbsp;◦ Functional correctness testing (unit tests)<br>&nbsp;&nbsp;&nbsp;&nbsp;◦ Code similarity / semantic correctness scoring<br>• Run experiments comparing:<br>&nbsp;&nbsp;&nbsp;&nbsp;◦ Zero-shot vs fine-tuned models<br>• Analyze performance gaps and failure cases |
| November | Optimization & Integration | • Improve dataset quality (add edge cases, error cases, difficult prompts)<br>• Iterate on model + evaluation pipeline<br>• Integrate outputs into a simple interface:<br>&nbsp;&nbsp;&nbsp;&nbsp;◦ CLI tool, notebook, or lightweight UI<br>• Produce final benchmarking report<br>• Prepare demo showcasing improved coding assistant performance |

> **Note for the team:** Please create a GitHub Projects board in this repository to break these milestones into weekly tasks. Go to the **Projects** tab → **New project** → Choose **Board** → Add columns for each month.

---

## 📊 Dataset

**Name and Source:** Harbor Framework public dataset
**Format:** CSV, JSON  
**Size:** under 1gb  
**Location:** GitHub (source of truth): https://github.com/harbor-framework/terminal-bench-2-1/tree/main/tasks
Hugging Face (easier plain-file download for Colab): https://huggingface.co/datasets/harborframework/terminal-bench-2.0

### Key Details
- Terminal-Bench is a benchmark and execution harness for evaluating how well AI agents perform real, end-to-end tasks in a sandboxed terminal environment (e.g., compiling code, debugging, resolving security issues), maintained by the Harbor project.
- Harbor (https://github.com/harbor-framework/harbor) is the companion framework used to run and score agents against the benchmark — it supports evaluating agents like Claude Code, OpenHands, and Codex CLI, and can generate rollouts usable for RL-style fine-tuning.
- Tasks and results are tracked on the public Harbor Hub leaderboard; students should review the repo's README and tasks/ directory for the task schema and scoring rubric before building on top of it.
- Related repos worth skimming for structure/format reference: terminal-bench-2-1 (current verified task set) and frontier-bench (successor benchmark with harder tasks).
---

## 🛠️ Suggested Approach

**ML Problem Type:** Natural Language Processing (NLP), Large Language Models (LLMs)/ Generative AI, Transfer Learning / Pre-trained Models

**Recommended Libraries:**
- pandas / numpy for data wrangling and prompt–response dataset construction
- Hugging Face transformers / datasets for loading and fine-tuning open-source LLMs
- pytest or task-specific test harnesses for functional correctness scoring
- docker (via the Harbor/Terminal-Bench harness) for sandboxed code execution
- OpenAI / Anthropic Python SDKs for baseline zero-shot / few-shot comparisons

**Evaluation Metrics:**
- Pass@k
- Unit test pass rate / functional correctness
- Code similarity metrics (e.g., CodeBLEU) for semantic correctness scoring
- Error-rate reduction vs. baseline model outputs

---

## 📚 Resources to Get Started

The following resources will help your team understand the problem space and potential technical approaches for this project:

**Background Reading:**
- Harbor framework overview and documentation: https://github.com/harbor-framework/harbor
- Terminal-Bench project overview: https://github.com/harbor-framework/terminal-bench

**Technical Tutorials:**
- Harbor Cookbook (end-to-end examples for running and building benchmarks): linked from the Harbor repo README
- Hugging Face documentation for fine-tuning and evaluating LLMs on code tasks

**Code Examples:**
- harbor-framework/terminal-bench-2-1 — current verified task set and submission workflow
- harbor-framework/frontier-bench — successor benchmark, useful reference for task structure

**Other:**
- Papers

Terminal-Bench 2.0 paper (the benchmark/dataset itself): Terminal-Bench 2.0 is a curated hard benchmark of 89 tasks in computer terminal environments, each with a unique environment, human-written solution, and comprehensive verification tests — https://arxiv.org/abs/2601.11868

Codex / HumanEval paper — introduces the Pass@k metric your Success Criteria section relies on: Codex is a GPT model fine-tuned on GitHub code, evaluated on HumanEval, a new set measuring functional correctness of programs synthesized from docstrings — https://arxiv.org/abs/2107.03374

CodeBLEU paper — the semantic similarity metric referenced in your Suggested Approach section: CodeBLEU absorbs the strength of BLEU in n-gram matching and further injects code syntax via abstract syntax trees and code semantics via data-flow — https://arxiv.org/abs/2009.10297 

Out of the BLEU" — good companion critique on why match-based metrics like CodeBLEU can diverge from human judgment: a study of six metrics — BLEU, ROUGE-L, METEOR, ChrF, CodeBLEU, and RUBY — found none reliably reflects human judgment on code quality when model score differences are small — https://arxiv.org/abs/2208.03133

Videos

"Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in CLI" (paper walkthrough) — https://www.youtube.com/watch?v=RRFeCml3mrQ

Benchtalks #1: Alex Shaw on Terminal-Bench & Harbor — good context on how/why the benchmark and harness were built — https://www.youtube.com/watch?v=UCn5gG0haCI

Docs/reference

Harbor framework docs (tutorial on running Terminal-Bench) — https://www.harborframework.com/docs/tutorials/running-terminal-bench

*Feel free to explore beyond these, and share anything interesting you find with me!*

---

## 🤝 How We'll Work Together

**Official check-ins:** During our biweekly 45-minute AI Studio Lab Section meeting block (2nd and 4th week of every month)

 **Other ways to reach out to me with questions:** 
* Your team's channel within Break Through Tech’s Discord space
* Rashmithimmaraju14@gmail.com; please copy your teammates and AI Studio Coach
* Request a team check-in on Zoom
* Note: I will aim to respond within 48 hours. Please reach out to your AI Studio Coach with urgent questions.


---

## 🚀 Getting Started

1. **Review this overview document** and note any questions for our first meeting
2. **Begin reviewing the dataset** using the link above
3. **Read the GitHub Projects documentation** [here](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)

I’m excited to work with you!

---

## ❓ Questions?

Please bring any questions to our first meeting during the week of August 24th (Break Through Tech’s Bridge to Studio - Session C). 

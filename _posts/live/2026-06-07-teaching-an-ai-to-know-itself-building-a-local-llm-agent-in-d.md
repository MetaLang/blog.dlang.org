---
title: "Teaching an AI to Know Itself: Building a Local LLM Agent in D"
author: Danny Arends

categories:
  - Community
  - Guest Posts
  - Project Highlights
  - Tutorials
  - Code
  - Machine Learning
---

I've been writing D for a long time. [DaNode](https://github.com/DannyArends/DaNode), my self-contained web server, has been running in production for over 12 years. [DImGui](https://github.com/DannyArends/DImGui) is a full SDL + Vulkan renderer that supports skeletal animations via the Open Asset Import Library, HDR lighting, and compute shaders, written entirely in D calling into external libraries via {% raw %}`importC`{% endraw %}. So when I decided to build a local agentic large language model (LLM) ([DLLM](https://github.com/DannyArends/DLLM)) from scratch, I'd sooner write it in Brainfuck than reach for Python. To be fair, the Python LLM ecosystem is enormous. However, by the time you have a working agent, you're sitting on top of a framework, which wraps a library, which calls into C++ via ctypes, which dispatches to CUDA kernels. Python all the way down to the metal, with several layers of abstraction you didn't write and can't easily debug. I wanted to understand what was actually happening.

*[DLLM](https://github.com/DannyArends/DLLM) is my latest D project: a minimal, clean coding agent built directly on llama.cpp. No Python, no bindings, no overhead.*

Here's a walkthrough of the two parts I'm most happy with: the {% raw %}`@Tool`{% endraw %} UDA registration system, and grammar-constrained sampling.

#### Starting Point: importC

Before anything else, the foundation. D's {% raw %}`importC`{% endraw %} lets you include C headers and use the API directly, as native D code. DLLM has one file, {% raw %}`includes.c`{% endraw %}, that pulls in the llama.cpp and mtmd headers. From there, {% raw %}`llama_decode`{% endraw %}, {% raw %}`llama_model_load_from_file`{% endraw %}, {% raw %}`llama_sampler_sample`{% endraw %}, the whole llama.cpp API, is available in D with full type safety and zero FFI overhead.

This is the same trick I used in DaNode to wrap OpenSSL, and an integral part of DImGui to call into Vulkan, SDL, the Open Asset Import Library, and shaderC. {% raw %}`importC`{% endraw %} is one of my favorite D features. I used to rely heavily on the Derelict & BindBC wrappers, and they were fantastic community contributions, but {% raw %}`importC`{% endraw %} has made them almost obsolete. No wrapper libraries, no binding maintenance, no surprises when the upstream C API updates.

#### The Tool System: Start With a Single UDA

An LLM agent is only useful if it can *act*. DLLM's tools cover web search, file I/O, Docker-sandboxed code execution, image download, date and time, text encoding, and audio playback. To *act*, it needs tools that it can control, and in DLLM you can create a new tool that the agent can use like this:

{% raw %}
```d
@Tool("Count how many times substring appears in text.")
string nOccurrences(string text, string substring) {
  try {
    return to!string(text.count(substring));
  } catch (Exception e) { return(format("Error: %s", e.msg)); }
}
```
{% endraw %}

The {% raw %}`@Tool(...)`{% endraw %} attribute is the entire registration step. No schema file to maintain, no separate dispatch table. The {% raw %}`Tool`{% endraw %} struct itself is trivial:

{% raw %}
```d
struct Tool {
  string description;
}
```
{% endraw %}

One string. That's the whole UDA definition. Everything else is derived from it and the function signature automatically. The description string is also used by the LLM agent to figure out what the tool is able to do.

#### Building Up: RegisterTools

At the top of each tool module, there's one line:

{% raw %}
```d
mixin RegisterTools;
```
{% endraw %}

This is a {% raw %}`mixin template`{% endraw %} that injects a {% raw %}`static this()`{% endraw %} module constructor. When the program starts, that constructor runs and populates a global tool definition array ({% raw %}`ToolDef[]`{% endraw %}) called {% raw %}`ALL_TOOLS`{% endraw %}. Here's how it works, step by step.

First, it gets a reference to the current module using the {% raw %}`__MODULE__`{% endraw %} string mixin trick:

{% raw %}
```d
mixin("alias ThisModule = " ~ __MODULE__ ~ ";");
```
{% endraw %}

Then it loops over every symbol in that module using {% raw %}`__traits(allMembers, ...)`{% endraw %} and {% raw %}`static foreach`{% endraw %}:

{% raw %}
```d
static foreach(name; __traits(allMembers, ThisModule)) {{
  mixin("alias member = " ~ name ~ ";");
  static if (is(typeof(member) == function)) {
    static if (hasUDA!(member, Tool)) {
```
{% endraw %}

For each function that has a {% raw %}`@Tool`{% endraw %} attribute, it extracts the description and the parameter names:

{% raw %}
```d
enum description = getUDAs!(member, Tool)[0].description;
alias ParamNames = ParameterIdentifierTuple!member;
```
{% endraw %}

{% raw %}`ParameterIdentifierTuple`{% endraw %} is a standard D trait that gives you the parameter names as a compile-time tuple: For {% raw %}`nOccurrences(string text, string substring)`{% endraw %} that's {% raw %}`["text", "substring"]`{% endraw %}. Then it builds an executor closure that unpacks the JSON arguments and calls the function:

{% raw %}
```d
auto executor = (JSONValue args) {
  string[] argValues;
  static foreach(paramName; ParamNames) { 
    argValues ~= args[paramName].type == JSONType.string ? 
                 args[paramName].str : 
                 args[paramName].toString(); 
  }
  // mixin generates: return member(argValues[0], argValues[1]);
  mixin(callStr);
};
ALL_TOOLS ~= ToolDef(name, description, parameters, executor);
```
{% endraw %}

So after startup, {% raw %}`ALL_TOOLS`{% endraw %}, the global tool definition array contains everything needed to both describe each tool to the LLM agent and allow it to be called by name at runtime. The function signature is the *single* source of truth.

#### What Gets Generated: System Prompt and Grammar

From {% raw %}`ALL_TOOLS`{% endraw %}, two things are auto-magically generated. First, {% raw %}`toolsToJSON()`{% endraw %} generates the JSON that goes into the system prompt, so the model knows what tools exist and what they can do:

{% raw %}
```json
[{
  "name": "nOccurrences",
  "description": "Count how many times substring appears in text.",
  "parameters": {
    "type": "object",
    "properties": {
      "text":      {"type": "string"},
      "substring": {"type": "string"}
    }
  }
}]
```
{% endraw %}

Second, {% raw %}`buildJsonGrammar()`{% endraw %} generates [a GBNF grammar](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) for constrained sampling. A GBNF grammar is a set of rules that define exactly what sequence of tokens (text) is valid. A simple example for a yes/no answer would look like:

{% raw %}
```d
root ::= "yes" | "no"
```
{% endraw %}
That's it, the sampler can now only produce the word "yes" or "no", nothing else. For DLLM's tool calls, the grammar is more complex but the principle is identical. The {% raw %}`toolname`{% endraw %} rule is generated dynamically from {% raw %}`ALL_TOOLS`{% endraw %}, so only real tool names are valid. Everything else follows standard JSON structure rules.

Unlike many Python-based agent frameworks, which handle tool calls with prompt engineering, output parsing, and prayer, grammar-constrained sampling gives an iron-clad guarantee that every tool call is structurally valid. The full GBNF grammar definition of valid JSON toolcalls is:

{% raw %}
```d
string buildJsonGrammar() {
  auto names = ALL_TOOLS.map!(t => "\"\\\"" ~ t.name ~ "\\\"\"").join(" | ");
  return(`
root ::= "{" ws "\"name\"" ws ":" ws toolname ws "," ws "\"arguments\"" ws ":" ws object ws "}</tool_call>"
toolname ::= ` ~ names ~ `
object ::= "{" ws (string ws ":" ws value (ws "," ws string ws ":" ws value)*)? ws "}"
array ::= "[" ws (value (ws "," ws value)*)? ws "]"
value ::= string | number | object | array | "true" | "false" | "null"
string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
number ::= "-"? ([0-9] | [1-9] [0-9]+) ("." [0-9]+)? ([eE] [-+]? [0-9]+)?
ws ::= [ \t\n\r]*
`);
}
```
{% endraw %}

The key part is the {% raw %}`toolname`{% endraw %} rule, which is generated dynamically from the global {% raw %}`ALL_TOOLS`{% endraw %} tool definition array. If you've registered {% raw %}`webSearch`{% endraw %}, {% raw %}`nOccurrences`{% endraw %}, and {% raw %}`countWords`{% endraw %}, the rule becomes:

{% raw %}
```
toolname ::= "\"webSearch\"" | "\"nOccurrences\"" | "\"countWords\""
```
{% endraw %}

The model can only produce a {% raw %}`name`{% endraw %} field that contains a tool that actually exists. The grammar enforces it at the logit level. This solves the model hallucinating non-existing tools or producing malformed JSON; it's structurally impossible.

#### The Sampler Switch

Two samplers (the component responsible for selecting the next token) are set up at startup. The conversational sampler runs at temperature 0.7 during normal thinking and output generation. The JSON sampler runs at a lower temperature (0.3), and crucially, has the grammar constraint attached:

{% raw %}
```d
llama_sampler_chain_add(model.json, llama_sampler_init_temp(0.3f));
llama_sampler_chain_add(model.json, llama_sampler_init_grammar(model.vocab, buildJsonGrammar().toStringz(), "root"));
llama_sampler_chain_add(model.json, llama_sampler_init_dist(LLAMA_DEFAULT_SEED));
```
{% endraw %}

During generation, the code watches for {% raw %}`<tool_call>`{% endraw %} and {% raw %}`</tool_call>`{% endraw %} tags in the output stream. Switching samplers is a single line:

{% raw %}
```d
auto sampler = (agent.json && inToolCall) ? agent.json : agent.sampler;
auto token = llama_sampler_sample(sampler, agent.ctx, -1);
```
{% endraw %}

The moment a {% raw %}`<tool_call>`{% endraw %} tag appears in the buffer, the grammar sampler takes over. The model *cannot* produce a malformed tool call while it's active. After {% raw %}`</tool_call>`{% endraw %} closes, the grammar sampler is reset and the conversational sampler takes over again.

No parsing heuristics, no fallback regex. Malformed tool calls are structurally impossible.

#### The Self-Knowledge Trick

The current version can read and reason about its own source code using just the Qwen 8B model. This isn't magic, it's [Retrieval-Augmented Generation (RAG)](https://en.wikipedia.org/wiki/Retrieval-augmented_generation). You can ask DLLM to index its own source code living in the *./src/* folder using the embedding model. Source code is chunked, chunks are tokenized, embedded using a dedicated CPU-resident Nomic embed model, and stored with cosine similarity scoring:

{% raw %}
```d
float cosineSimilarity(float[] a, float[] b) {
  float denom = sqrt(a.map!(x=>x*x).sum) * sqrt(b.map!(x=>x*x).sum);
  return denom == 0.0f ? 0.0f : dotProduct(a, b) / denom;
}
```
{% endraw %}

The index is binary-persisted between sessions using {% raw %}`rawWrite`{% endraw %} and {% raw %}`rawRead`{% endraw %}, with a magic number to catch stale files. When you ask a question, the top-k most relevant chunks are retrieved and injected into context.

What makes it interesting is what's being indexed. Because every tool is a plain D function with a {% raw %}`@Tool`{% endraw %} attribute, the source files are already their own documentation. The model doesn't have to reverse-engineer intent from implementation. The description is right there in the attribute, and the implementation is a few lines below it.

*The practical result: you can ask "how does web search work?" and the agent retrieves the {% raw %}`webSearch`{% endraw %} function, reads the {% raw %}`@Tool`{% endraw %} description, and explains it accurately. With a small model. Locally.*

#### What's Included
DLLM is more than just the tool system and grammar sampler. Here's everything that's included out of the box:
* RAG with binary-persisted embeddings and cosine similarity ranking
* Vision support via mtmd (load an image, ask about it)
* Docker-sandboxed code execution (Python, JavaScript, Bash, R, D)
* Web search via SearxNG, and web fetch
* File I/O, date/time, encoding, audio playback tools
* KV cache condensation via a dedicated summary model
* Thinking budget enforcement via token limits
* Memento system, where the agent writes notes to its future self between sessions
* Full interactive and oneshot modes

#### In closing

D gave me {% raw %}`ImportC`{% endraw %} for zero-overhead access to llama.cpp, UDAs and {% raw %}`__traits`{% endraw %} for a tool system with one source of truth, and UFCS for code that reads the way I think. The entire tool registration and grammar generation system is about 150 lines.

If you've been looking for a project to try D on, local AI tooling is a good fit. The space is young, the performance characteristics reward D's zero-overhead philosophy, and the metaprogramming needs of LLM agents map almost perfectly onto what D does best.

DLLM is open source under GPLv3. The code is small enough to read in an afternoon. Find it at [github.com/DannyArends/DLLM](https://github.com/DannyArends/DLLM).

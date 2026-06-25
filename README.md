# booktime
an AI book writing web interface. using ollama and lm studios. two different models. using a form based webpage you creat your characters , set the plot add your twists and turns set the tone and send it off to your book director, a small assistant type ai that keeps track of the story, saving it in text file, and formoating the form info into your chaoter, you decide the who and the whats of the story let lm studios fill in th e rest. your story will depend on the models you use and ythe weigts you set the models at, but now all the dertails get there in a way that is ideal for writing. if writing somethinh a little edgy, uncensorted models on both ends to keep from having issues.

## Model Downloads

Book Time checks LM Studio with `lms ps` and shows the currently loaded writing model on the setup page.

- LM Studio writing model currently used: [Gemma The Writer N Restless Quill 10B Uncensored GGUF](https://huggingface.co/DavidAU/Gemma-The-Writer-N-Restless-Quill-10B-Uncensored-GGUF)
- Small Book Time/Ollama assistant option: [Qwen2.5 0.5B Instruct GGUF](https://huggingface.co/lmstudio-community/Qwen2.5-0.5B-Instruct-GGUF/tree/main)
- Ollama download: [ollama.com/download](https://ollama.com/download)
- LM Studio download: [lmstudio.ai/download](https://lmstudio.ai/download)

Optional Ollama command for the writing model:

```powershell
ollama run hf.co/DavidAU/Gemma-The-Writer-N-Restless-Quill-10B-Uncensored-GGUF:Q4_K_M
```

Full install and setup notes are in [booktime/README.md](booktime/README.md).

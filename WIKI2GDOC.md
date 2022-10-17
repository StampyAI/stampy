# `wiki2gdoc.py`

Requirements:

- pydrive is installed
- `questions.txt` in the main directory with each question title as in a separate line
- `GDRIVE_FOLDER_ID` in `.env` is set to "1huMo_uttHa8qI0ASnu9_jfNRK4rce9pU"
- you can see [this folder](https://drive.google.com/drive/folders/1huMo_uttHa8qI0ASnu9_jfNRK4rce9pU)
  - if not, ask Rob to share it with you
- `client_secrets.json` created and generated according to [this guide](https://d35mpxyw7m7k7g.cloudfront.net/bigdata_1/Get+Authentication+for+Google+Service+API+.pdf)
  - you will also need to enable yourself as a test developer (guide [here](https://www.youtube.com/watch?v=x_NPvk0pk8g))

If everything is set up, just

```py
python3 wiki2gdoc.py
```

Every question will be uploaded as an `.odt` file to the GDrive folder. If the question has a canonical answer, that answer will be added as a paragraph. If there is no canonical answer, noncanonical answers will be added as separate paragraphs under H2 headings.

Most conversion issues are most likely caused by improper formatting in the database (e.g. tags are mixed with the answer text content).

One thing that may be worth improving is automatic conversion of markdown-style links into embedded GDoc links.

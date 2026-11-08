# Understanding and developing Pairwise Lab

## Start with a real review

1. Install Python 3.11 or newer if it is not already available.
2. In a terminal, open this project folder.
3. Run `python server.py --seed examples/comparisons.json` once.
4. Run `python server.py` and open http://127.0.0.1:8000.
5. Review the Python example. Try the list `[8, 2, 5]`: sorting it changes both its order and the meaning of “first.” Check which response respects the prompt.
6. Save your scores and explanation. Notice that model names appear only afterward.
7. Reload the page and confirm your review persists.
8. Export the review and inspect its JSON.

## Follow one request through the code

- `static/index.html` contains the workspace structure.
- `static/style.css` handles its appearance and small-screen layout.
- `static/app.js` collects your form values and posts them to `/api/reviews/{id}`.
- `server.py` validates the HTTP request and calls the persistence layer.
- `store.py` validates scores, stores the immutable review in SQLite, and reveals the model mapping.
- `tests/test_app.py` checks the rules and exercises real local HTTP requests.

Try explaining why hiding model names only in the page would be weaker than removing them from the pending-review API response.

## A manageable first contribution

Add a fourth synthetic comparison on a topic you know well. Write two responses that differ in one meaningful way and explain that difference. Import it, review it, and check the export.

Then choose a code change: category filtering is a useful next feature. Decide whether filtering should affect just the queue or also the results table. Implement that behavior, add an appropriate regression test, and describe the choice in your commit.

## Terminal and Git basics

After cloning your published repository:

```bash
git status
python -m unittest discover -s tests -v
git diff
git add examples/comparisons.json
git commit -m "Add a new evaluation example"
git push
```

Replace the file in `git add` with the files you actually changed. Use your own configured Git author identity. Review the diff before committing. Do not commit your SQLite data file or private evaluation data.

## Honest application positioning

This is a new project built with AI assistance. It has a working local backend, database, browser interface, blind comparison workflow, imports, exports, and automated backend/API tests. It does not yet generate model responses, support multiple reviewers, or have automated browser tests.

Before submitting, use it, make meaningful changes, and be able to explain the design and limitations in your own words. A fresh repository may not meet this employer's threshold for a substantial actively developed project yet; real development work and your understanding matter more than the number of files or commits.

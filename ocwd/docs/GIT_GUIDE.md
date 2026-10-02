# How to commit, push and publish this project with Git

This guide is written for this repository
(`https://github.com/Bhargavteja-9779/FOAE-Fault-Origin-Attribution-Engine`) and for
the work branch `claude/obdii-wear-detection-dataset-c3g668`.

---

## 0. One-time setup (on your own computer)

```bash
# Install Git: https://git-scm.com/downloads  (Windows: "Git for Windows")
git --version

# Tell Git who you are (appears in every commit)
git config --global user.name  "P N Bhargav Teja"
git config --global user.email "your-github-email@example.com"

# Windows only: keep line endings sane
git config --global core.autocrlf true
```

GitHub no longer accepts your account password for `git push`. Use one of these:

* **GitHub Desktop** (simplest): <https://desktop.github.com>. Sign in, and it handles the login.
* **Personal access token:** GitHub → Settings → Developer settings → Personal access tokens →
  *Fine-grained token* with **Contents: Read and write** on this repository. Paste it when Git
  asks for a password.
* **SSH key:** `ssh-keygen -t ed25519`, then add the `.pub` file under GitHub → Settings → SSH keys,
  and use the `git@github.com:...` URL.

---

## 1. Get the code onto your computer

### 1a. If you do not have the repository yet

```bash
git clone https://github.com/Bhargavteja-9779/FOAE-Fault-Origin-Attribution-Engine.git
cd FOAE-Fault-Origin-Attribution-Engine
```

### 1b. Restore the work from the bundle file Claude sent you

The cloud session could not push (GitHub refused access), so all commits were delivered as a
bundle file, e.g. `ocwd-commits-v4.bundle`. Put it in the repository folder, then:

```bash
git bundle verify ocwd-commits-v4.bundle          # should end with "is okay"
git fetch ocwd-commits-v4.bundle \
    claude/obdii-wear-detection-dataset-c3g668:claude/obdii-wear-detection-dataset-c3g668
git switch claude/obdii-wear-detection-dataset-c3g668
git log --oneline -8                              # you should see the OCWD commits
```

---

## 2. Push the branch to GitHub

```bash
git push -u origin claude/obdii-wear-detection-dataset-c3g668
```

If a push is rejected because of the `.github/workflows` file, your token needs the
**Workflows** permission (fine-grained token: *Workflows: Read and write*).

---

## 3. Everyday workflow: change, commit, push

```bash
git status                       # what changed?
git diff                         # see the exact changes
git add paper/main.tex           # stage specific files ...
git add -A                       # ... or everything
git commit -m "Add author biographies and corresponding e-mail"
git push                         # sends commits to GitHub
```

Good commit messages say *what* and *why* in the first line (≤ 72 characters), e.g.
`Fix reference volume for Shen et al. 2018`.

Undo mistakes safely:

| Situation | Command |
|---|---|
| Unstage a file you added by mistake | `git restore --staged <file>` |
| Throw away uncommitted edits to a file | `git restore <file>` |
| Fix the message of the last (unpushed) commit | `git commit --amend` |
| Undo a pushed commit without rewriting history | `git revert <commit-sha>` |

Never commit the datasets: `data/raw` and `data/cache` are already in `.gitignore`.

---

## 4. Merge into `main` (pull request)

1. On GitHub, open the repository. A banner offers **"Compare & pull request"** for the
   branch; click it (or go to *Pull requests → New*).
2. Base: `main`, compare: `claude/obdii-wear-detection-dataset-c3g668`.
3. Title: `OCWD: OBD-II connector wear detection study and IEEE Access manuscript`.
4. **Create pull request**. The `ocwd-tests` GitHub Action runs the 14 unit tests automatically.
5. When it is green, click **Merge pull request**.

Command-line alternative:

```bash
git switch main
git pull
git merge --no-ff claude/obdii-wear-detection-dataset-c3g668
git push
```

---

## 5. Make the code public and citable (recommended for reviewers)

The paper's *Data and Code Availability* section links to this repository, so reviewers must be
able to open it:

1. **Visibility:** GitHub → Settings → General → *Danger zone* → **Change visibility → Public**
   (or keep it private and add reviewers as collaborators on request).
2. **License:** the repository's `LICENSE` file currently says *"Proprietary – all rights
   reserved"*, which contradicts "code is publicly available". Decide with your co-authors (and,
   if needed, your patent agent). Common choices: MIT (permissive) or Apache-2.0 (permissive,
   with a patent clause). To apply one, replace `LICENSE` with the standard text from
   <https://choosealicense.com>, then commit.
3. **Release + DOI (Zenodo):**
   * Sign in to <https://zenodo.org> with GitHub, and enable the repository under
     *GitHub → Repository toggle*.
   * On GitHub: *Releases → Draft a new release*, tag `v1.0-ieee-access`, then publish.
   * Zenodo archives the release and issues a DOI. Cite that DOI in the paper's code-availability
     sentence (e.g. `\url{https://doi.org/10.5281/zenodo.XXXXXXX}`).

Tagging from the command line:

```bash
git tag -a v1.0-ieee-access -m "Code for the IEEE Access submission"
git push origin v1.0-ieee-access
```

---

## 6. Updating the paper after reviews

```bash
git switch -c revision-1            # new branch for the revision
# edit paper/sections/*.tex, rerun experiments if needed
cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main && cd ..
git add -A && git commit -m "Revision 1: address reviewer comments"
git push -u origin revision-1
```

Use `paper/response_to_reviewers.tex` to answer each comment point by point.

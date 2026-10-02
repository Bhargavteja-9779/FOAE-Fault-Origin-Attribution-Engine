"""Convert the LaTeX manuscript (and companions) to editable Word documents.

    cd paper && python word/make_word.py

Cross-reference numbers are taken from the compiled .aux files, so figure,
table, equation and section numbers match the PDF. The LaTeX PDF remains the
version of record for submission; the .docx files are editable copies.
"""
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
UNITS = {r"\ohm": "Ω", r"\milli\second": "ms", r"\micro\second": "µs", r"\second": "s", r"\per\second": "s⁻¹"}


def labels(aux):
    out = {}
    for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{(.*?)\}\{", Path(aux).read_text(encoding="utf-8", errors="ignore")):
        v = re.sub(r"\\mbox\s*", "", m.group(2)).replace("{", "").replace("}", "")
        out[m.group(1)] = v
    return out


def expand(tex, base):
    def rep(m):
        name = m.group(2)
        p = base / (name if name.endswith(".tex") else name + ".tex")
        return expand(p.read_text(encoding="utf-8"), base)
    return re.sub(r"\\(input|tinput)\{([^}]*)\}", rep, tex)


def algorithm_to_list(tex):
    def rep(m):
        body = m.group(0)
        cap = re.search(r"\\caption\{([^}]*)\}", body).group(1)
        req = re.search(r"\\REQUIRE (.*)", body)
        ens = re.search(r"\\ENSURE (.*)", body)
        steps = re.findall(r"\\STATE (.*)", body)
        s = f"\n\n\\textbf{{Algorithm 1: {cap}}}\n\n"
        if req:
            s += f"\\textbf{{Input:}} {req.group(1)}\n\n"
        if ens:
            s += f"\\textbf{{Output:}} {ens.group(1)}\n\n"
        s += "\\begin{enumerate}\n" + "".join(f"\\item {x}\n" for x in steps) + "\\end{enumerate}\n\n"
        return s
    return re.sub(r"\\begin\{algorithm\}.*?\\end\{algorithm\}", rep, tex, flags=re.S)


def clean(tex, L):
    tex = algorithm_to_list(tex)
    tex = re.sub(r"\\resizebox\{[^}]*\}\{!\}\{%?\s*", "", tex)
    tex = tex.replace("\\end{tabular}}", "\\end{tabular}")
    tex = re.sub(r"\\multicolumn\{(\d+)\}\{@\{\}l\}", r"\\multicolumn{\1}{l}", tex)
    tex = tex.replace("\\scriptsize ", "")
    tex = tex.replace("{table*}", "{table}").replace("{figure*}", "{figure}")
    tex = re.sub(r"\\cmidrule(\([^)]*\))?\{[^}]*\}", "", tex)
    tex = re.sub(r"\\multirow\{\d+\}\{\*\}\{([^}]*)\}", r"\1", tex)
    tex = re.sub(r"\\setlength\{\\tabcolsep\}\{[^}]*\}", "", tex)
    tex = re.sub(r"\\PARstart\{(\w)\}\{(\w+)\}", r"\1\2", tex)
    tex = re.sub(r"\\includegraphics(\[[^\]]*\])?\{([^}]*?)(\.pdf)?\}", lambda m: f"\\includegraphics[width=6in]{{word/fig/{Path(m.group(2)).stem}.png}}", tex)
    for u, s in UNITS.items():
        tex = re.sub(r"\\SI\{([^}]*)\}\{" + re.escape(u) + r"\}", lambda m: f"{m.group(1)} {s}", tex)

    # captions get their PDF numbers
    def cap_number(env, prefix):
        def rep(m):
            body = m.group(0)
            lab = re.search(r"\\label\{([^}]*)\}", body)
            n = L.get(lab.group(1), "") if lab else ""
            return body.replace("\\caption{", f"\\caption{{{prefix}~{n}. ", 1)
        return rep
    tex = re.sub(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", cap_number("figure", "Fig."), tex, flags=re.S)
    tex = re.sub(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", cap_number("table", "TABLE"), tex, flags=re.S)

    # numbered equations -> display math with an explicit number
    def eq(m):
        body = m.group(1)
        lab = re.search(r"\\label\{([^}]*)\}", body)
        n = L.get(lab.group(1), "") if lab else ""
        body = re.sub(r"\\label\{[^}]*\}", "", body).strip().rstrip(",.")
        return f"\n$$ {body} \\qquad ({n}) $$\n"
    tex = re.sub(r"\\begin\{equation\}(.*?)\\end\{equation\}", eq, tex, flags=re.S)

    def align(m):
        out = []
        for line in re.split(r"\\\\", m.group(1)):
            if not line.strip():
                continue
            lab = re.search(r"\\label\{([^}]*)\}", line)
            n = L.get(lab.group(1), "") if lab else ""
            line = re.sub(r"\\label\{[^}]*\}", "", line).replace("&", "").strip().rstrip(",")
            out.append(f"$$ {line} \\qquad ({n}) $$")
        return "\n" + "\n\n".join(out) + "\n"
    tex = re.sub(r"\\begin\{align\}(.*?)\\end\{align\}", align, tex, flags=re.S)
    tex = re.sub(r"\\(eq)?ref\{([^}]*)\}", lambda m: L.get(m.group(2), "?"), tex)
    tex = tex.replace("~", " ")
    return tex


def main_paper():
    L = labels(PAPER / "main.aux")
    m = (PAPER / "main.tex").read_text(encoding="utf-8")
    title = re.search(r"\\title\{(.*?)\}\n", m, re.S).group(1)
    abstract = expand((PAPER / "sections/abstract.tex").read_text(encoding="utf-8"), PAPER)
    kw = re.search(r"\\begin\{keywords\}(.*?)\\end\{keywords\}", abstract, re.S).group(1).strip()
    abs_txt = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", abstract, re.S).group(1).strip()
    corresp = re.search(r"\\corresp\{(.*?)\}\n", m).group(1)
    addr = re.search(r"\\address\[1\]\{(.*?)\}\n", m).group(1)
    body = ""
    for sec in ("intro", "related", "model", "method", "setup", "results", "discussion"):
        body += expand((PAPER / f"sections/{sec}.tex").read_text(encoding="utf-8"), PAPER) + "\n"
    bios = re.findall(r"\\begin\{IEEEbiography\}\{([^}]*)\}(.*?)\\end\{IEEEbiography\}", m, re.S)
    biotex = "\\section*{Author Biographies}\n" + "".join(f"\\textbf{{{n}}} {t.strip()}\n\n" for n, t in bios)
    doc = (r"\documentclass{article}\usepackage{amsmath,amssymb,graphicx,booktabs,url}"
           + f"\\title{{{title}}}\\author{{P. N. Bhargav Teja, Lanka Sree Chathurya, K. Arun Reddy, and Ragavan K\\\\ {addr}\\\\ {corresp}}}\\date{{}}"
           + "\\begin{document}\\maketitle\n"
           + f"\\textbf{{Abstract}}---{abs_txt}\n\n\\textbf{{Index Terms}}---{kw}\n\n"
           + body + "\n\\section*{References}\n" + biotex + "\\end{document}\n")
    doc = clean(doc, L)
    flat = HERE / "main_flat.tex"
    flat.write_text(doc, encoding="utf-8")
    run(flat, PAPER / "word" / "Manuscript_IEEE_Access.docx", bib=True)


def simple(src, dst, aux=None):
    L = labels(aux) if aux and Path(aux).exists() else {}
    t = expand((PAPER / src).read_text(encoding="utf-8"), PAPER)
    flat = HERE / (Path(src).stem + "_flat.tex")
    flat.write_text(clean(t, L), encoding="utf-8")
    run(flat, PAPER / "word" / dst, bib=False)


def run(flat, out, bib):
    cmd = ["pandoc", str(flat), "-f", "latex", "-o", str(out), "--resource-path", str(PAPER)]
    if bib:
        cmd += ["--citeproc", "--bibliography", str(PAPER / "refs.bib"), "--csl", str(HERE / "ieee.csl"),
                "-M", "reference-section-title=References", "-M", "link-citations=true"]
    subprocess.run(cmd, check=True, cwd=PAPER)
    print("wrote", out)


if __name__ == "__main__":
    main_paper()
    simple("cover_letter.tex", "Cover_Letter.docx")
    simple("supplementary.tex", "Supplementary_Material.docx", PAPER / "supplementary.aux")
    simple("response_to_reviewers.tex", "Response_to_Reviewers_Template.docx")

#!/bin/bash
# LambdaJobsAI v2 — AI-Powered Resume Generator
# Double-click in Finder to launch.

cd "$(dirname "$0")"

# Extend PATH for Homebrew, pyenv, nvm
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.pyenv/shims:$PATH"
[ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh" 2>/dev/null || true
if [ -d "$HOME/.nvm/versions/node" ]; then
    _latest_node=$(ls "$HOME/.nvm/versions/node" 2>/dev/null | sort -V | tail -1)
    [ -n "$_latest_node" ] && export PATH="$HOME/.nvm/versions/node/$_latest_node/bin:$PATH"
fi

# ── Colors ─────────────────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'
C='\033[0;36m'; B='\033[1m'; D='\033[2m'; X='\033[0m'

banner() {
    clear
    echo -e "${B}${C}"
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║         LambdaJobsAI  v2.0                ║"
    echo "  ║   AI-Powered Resume & Cover Letter Gen    ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo -e "${X}"
}

# ── Find Python 3.10+ ──────────────────────────────────────────────────────
PYTHON=""
for _py in python3 python3.13 python3.12 python3.11 python3.10 python; do
    if command -v "$_py" &>/dev/null; then
        _ok=$("$_py" -c "import sys; print(sys.version_info>=(3,10))" 2>/dev/null)
        [ "$_ok" = "True" ] && PYTHON="$_py" && break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${R}  Python 3.10+ not found.${X}  brew install python3"
    read -n 1 -s -r -p "  Press any key..."
    exit 1
fi

# ── Detect installed AI CLIs ───────────────────────────────────────────────
MODELS=(); MODEL_LABELS=()
command -v claude    &>/dev/null && MODELS+=("claude")    && MODEL_LABELS+=("Claude   (Anthropic)")
command -v gemini    &>/dev/null && MODELS+=("gemini")    && MODEL_LABELS+=("Gemini   (Google)")
command -v codex     &>/dev/null && MODELS+=("codex")     && MODEL_LABELS+=("Codex    (OpenAI)")
command -v opencode  &>/dev/null && MODELS+=("opencode")  && MODEL_LABELS+=("OpenCode")

# ── Init DB once ───────────────────────────────────────────────────────────
"$PYTHON" lambda.py init 2>/dev/null || true

# ── Model selection ─────────────────────────────────────────────────────────
banner

if [ ${#MODELS[@]} -eq 0 ]; then
    echo -e "${R}  No AI CLI detected.${X}\n"
    echo "  Install at least one:"
    echo "    claude:    npm i -g @anthropic-ai/claude-code"
    echo "    gemini:    npm i -g @google/gemini-cli"
    echo "    codex:     npm i -g @openai/codex"
    read -n 1 -s -r -p "  Press any key..."
    exit 1
fi

echo -e "${C}  Detected AI models:${X}"
for _i in "${!MODELS[@]}"; do
    echo "    $((_i+1)). ${MODEL_LABELS[$_i]}"
done
echo ""
read -rp "  Select model [1]: " MODEL_IDX
MODEL_IDX=${MODEL_IDX:-1}

if ! [[ "$MODEL_IDX" =~ ^[0-9]+$ ]] || \
   [ "$MODEL_IDX" -lt 1 ] || \
   [ "$MODEL_IDX" -gt "${#MODELS[@]}" ]; then
    echo -e "${R}  Invalid choice.${X}"
    exit 1
fi

SELECTED_CLI="${MODELS[$((MODEL_IDX-1))]}"
SELECTED_LABEL="${MODEL_LABELS[$((MODEL_IDX-1))]}"

# ── Build prompt file ───────────────────────────────────────────────────────
# Writes a self-contained prompt that embeds all context the AI needs.
build_prompt() {
    local jd_file="$1" job_url="$2" with_cover="$3" out="$4"

    {
        cat << 'PREAMBLE'
You are an expert resume writer and career coach.
Your working directory is set. Follow ALL rules in the AGENT RULES section exactly.
Complete the full 5-step pipeline without skipping any step.
PREAMBLE

        echo ""
        echo "Working directory: $(pwd)"
        echo ""
        echo "══════════════════════════════════════════════════════════"
        echo " AGENT RULES  (from AGENT.md — read every word)"
        echo "══════════════════════════════════════════════════════════"
        cat AGENT.md

        echo ""
        echo "══════════════════════════════════════════════════════════"
        echo " MASTER RESUME  (resume.json — source of truth)"
        echo "══════════════════════════════════════════════════════════"
        cat resume.json

        echo ""
        echo "══════════════════════════════════════════════════════════"
        echo " RESUME CONTEXT  (RESUME.md)"
        echo "══════════════════════════════════════════════════════════"
        cat RESUME.md

        echo ""
        echo "══════════════════════════════════════════════════════════"
        echo " JOB DESCRIPTION"
        echo "══════════════════════════════════════════════════════════"
        cat "$jd_file"

        if [ -n "$job_url" ]; then
            echo ""
            echo "══════════════════════════════════════════════════════════"
            echo " JOB URL"
            echo "══════════════════════════════════════════════════════════"
            echo "$job_url"
        fi

        echo ""
        echo "══════════════════════════════════════════════════════════"
        echo " YOUR TASK"
        echo "══════════════════════════════════════════════════════════"
        cat << TASK
Step 1 — Parse: Extract company, job_title, slug, required_skills, role_angle from the JD.
         company must never be "Unknown". If unclear, make your best inference.

Step 2 — Tailor resume.json:
         • Rewrite summary only (2–3 sentences, role-specific, no clichés).
         • Reorder bullets in each experience so JD-relevant ones come first.
         • Bullets are VERBATIM from resume.json — do NOT rewrite or merge them.
         • Push JD keywords to the front of skill categories.
         • Never invent skills, employers, metrics, or dates.

Step 3 — Write these files (create output/<slug>/ directory first):
         • output/<slug>/application.json    (tailored resume, same schema as resume.json)
         • output/<slug>/cover_letter.txt    (see cover letter instruction below)
         • output/<slug>/keyword_report.json ({"matched_keywords":[...],"missing_keywords":[...]})
         • output/<slug>/job_description.txt (raw JD text)

TASK

        if [ "$with_cover" = "yes" ]; then
            cat << COVER_YES
Cover letter (cover_letter.txt):
         Write 3 short paragraphs in order:
           1. Why the role fits the candidate.
           2. Why the candidate fits the company (use concrete facts from resume.json only).
           3. A clear call-to-action for a conversation.
         Tone: confident, direct, specific.
         BANNED words: passionate, results-driven, synergy, ecosystem, leverage,
                       holistic, guru, rockstar, ninja, world-class.
COVER_YES
        else
            echo "Cover letter: user declined — write an EMPTY cover_letter.txt file."
        fi

        cat << FINALIZE

Step 4 — Run EXACTLY this command (fill in <slug>, <Company Name>, <Job Title>):

  python3 lambda.py finalize \\
    --tailored  output/<slug>/application.json \\
    --cover     output/<slug>/cover_letter.txt \\
    --company   "<Company Name>" \\
    --title     "<Job Title>" \\
    --url       "$job_url" \\
    --jd-file   output/<slug>/job_description.txt \\
    --keywords  output/<slug>/keyword_report.json \\
    --runtime   "$SELECTED_CLI" \\
    --addressee "Hiring Team"

  This command compiles LaTeX PDFs (1 page enforced) and writes the database.
  Do NOT skip it — the dashboard will not see the application otherwise.

Step 5 — Run: python3 lambda.py list
         Confirm the new application appears at the top.

HARD RULES (never break):
  • Resume PDF = exactly 1 page (XeLaTeX enforces via \vspace scaling).
  • No invented data of any kind.
  • Bullets verbatim — reorder only.
  • Only summary is fully rewritten.
  • Run lambda.py finalize — no exceptions.
FINALIZE
    } > "$out"
}

# ── Invoke selected AI CLI ──────────────────────────────────────────────────
run_ai() {
    local pf="$1"
    case "$SELECTED_CLI" in
        claude)
            # Claude Code CLI — dangerously-skip-permissions matches default Mac launch behavior
            claude -p "$(cat "$pf")" --allowedTools "Bash,Write,Read,Edit" --dangerously-skip-permissions
            ;;
        gemini)
            cat "$pf" | gemini --yolo
            ;;
        codex)
            codex --yolo "$(cat "$pf")"
            ;;
        opencode)
            echo -e "${Y}  OpenCode is interactive.${X}"
            echo "  Copy the full prompt below, paste it into OpenCode:"
            echo ""
            echo "  ═══════════════════════════════════════════════════"
            cat "$pf"
            echo "  ═══════════════════════════════════════════════════"
            echo ""
            read -rp "  Press Enter to open OpenCode (then paste the prompt)..."
            opencode
            ;;
    esac
}

# ── Main menu loop ──────────────────────────────────────────────────────────
while true; do
    banner
    echo -e "  ${G}Model: $SELECTED_LABEL${X}\n"
    echo -e "${B}  ────────────────────────────${X}"
    echo "  1. Generate Resume"
    echo "  2. Open Dashboard"
    echo "  3. Exit"
    echo -e "${B}  ────────────────────────────${X}\n"
    read -rp "  > " CHOICE

    case "$CHOICE" in

        1)  # ── Generate Resume ──────────────────────────────────────────
            echo ""
            echo -e "${C}  Paste job description — press Ctrl+D when done:${X}\n"

            JD_FILE="/tmp/lambdajobs_jd_$$.txt"
            cat > "$JD_FILE"

            if [ ! -s "$JD_FILE" ]; then
                echo -e "${R}  Nothing pasted. Try again.${X}"
                rm -f "$JD_FILE"
                sleep 1
                continue
            fi

            echo ""
            read -rp "  Job URL (blank to skip): " JOB_URL
            JOB_URL="${JOB_URL:-}"

            echo ""
            read -rp "  Generate cover letter too? (Y/n): " COVER_ANS
            WITH_COVER="no"
            [[ "${COVER_ANS:-Y}" =~ ^[Yy] ]] && WITH_COVER="yes"

            PROMPT_FILE="/tmp/lambdajobs_prompt_$$.txt"
            build_prompt "$JD_FILE" "$JOB_URL" "$WITH_COVER" "$PROMPT_FILE"
            rm -f "$JD_FILE"

            echo ""
            echo -e "${C}  Running $SELECTED_LABEL — takes ~30–90 seconds...${X}\n"
            run_ai "$PROMPT_FILE"
            rm -f "$PROMPT_FILE"

            echo ""
            echo -e "${G}  ✓ Done!${X}  Files in output/"
            echo -e "${D}  Open dashboard → option 2${X}"
            echo ""
            read -n 1 -s -r -p "  Press any key..."
            ;;

        2)  # ── Dashboard ────────────────────────────────────────────────
            echo ""
            echo -e "${C}  Starting dashboard server...${X}"
            "$PYTHON" server.py &
            _srv_pid=$!
            sleep 1
            open "http://localhost:7421" 2>/dev/null || \
            xdg-open "http://localhost:7421" 2>/dev/null || true
            echo -e "${G}  Dashboard: http://localhost:7421  (PID $_srv_pid)${X}"
            echo -e "${D}  Stop server: kill $_srv_pid${X}"
            echo ""
            read -n 1 -s -r -p "  Press any key..."
            ;;

        3)  # ── Exit ─────────────────────────────────────────────────────
            echo ""
            echo "  Goodbye."
            exit 0
            ;;

        *)
            echo -e "${R}  Enter 1, 2, or 3.${X}"
            sleep 0.5
            ;;
    esac
done

FROM python:3.11-slim

# Install LaTeX (pdflatex) and system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-lang-german \
        texlive-fonts-recommended \
        texlive-fonts-extra \
        texlive-pictures \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies into a virtual env (survives volume mount at /app)
COPY requirements.txt .
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/opt/venv/bin:$PATH"

# Run the full pipeline (CSV → JSON → maps → LaTeX → PDF)
ENTRYPOINT ["python3", "src/main.py"]

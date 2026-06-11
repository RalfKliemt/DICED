FROM python:3.11-slim

WORKDIR /app

# Copy the whole repo
COPY . .

# Install the package (Flask is pulled in as a dependency)
RUN pip install --no-cache-dir -e .

# HF Spaces requires the app to listen on port 7860
ENV PORT=7860

EXPOSE 7860

CMD ["python", "-c", "from diced.web import app; app.run(host='0.0.0.0', port=7860)"]

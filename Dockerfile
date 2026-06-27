# --- Stage 1: Build the Frontend ---
FROM node:18-alpine AS frontend-builder
WORKDIR /frontend-build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Stage 2: Serve with the Backend ---
FROM python:3.10-slim
WORKDIR /code

# Install dependencies
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn python-multipart

# Set up Hugging Face non-root user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

# Copy all files over
COPY --chown=user . $HOME/app

# Copy built frontend directly into the 'static' folder inside root app
COPY --from=frontend-builder --chown=user /frontend-build/dist $HOME/app/static

EXPOSE 7860

# We set PYTHONPATH to the current directory ($HOME/app) so Python can seamlessly find 'api' and 'src' modules
ENV PYTHONPATH=$HOME/app

# Start the application using standard module notation
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
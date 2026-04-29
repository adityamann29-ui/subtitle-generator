# using python 3.10 as base image
FROM python:3.10-slim

# set working directory inside container
WORKDIR /app

# install system dependencies
# ffmpeg is needed for moviepy/audio extraction
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# copy requirements first
# this way docker caches this layer
COPY requirements.txt .

# install python packages
RUN pip install --no-cache-dir -r requirements.txt

# copy all project files
COPY . .

# create upload and output folders
RUN mkdir -p uploads outputs

# expose port 5000
EXPOSE 5000

# run the app
CMD ["python", "app.py"]
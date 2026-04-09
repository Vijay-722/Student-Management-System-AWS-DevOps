# Use Python base image
FROM python:3.10

# Set working directory
WORKDIR /app

# Copy files
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Expose port
EXPOSE 5001

# Run app using Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5001", "app:app"]

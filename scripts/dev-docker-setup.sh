#!/bin/bash

# Development Docker Setup Script for Ollama Integration
# This script sets up the development environment with Docker + Ollama

set -e

echo "🚀 Setting up Docker development environment with Ollama integration..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if Ollama is running locally
echo "🔍 Checking if Ollama is running locally..."
if ! curl -s http://localhost:11434/api/version >/dev/null 2>&1; then
    echo "❌ Ollama is not running on localhost:11434"
    echo "Please start Ollama with: ollama serve"
    echo "Or install Ollama from: https://ollama.com"
    exit 1
fi

echo "✅ Ollama is running locally"

# Check if required model is available
echo "🔍 Checking if llama3:latest is available..."
if ! ollama list | grep -q "llama3:latest"; then
    echo "📥 Pulling llama3:latest model..."
    ollama pull llama3:latest
else
    echo "✅ llama3:latest model is available"
fi

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📄 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file to configure your settings"
else
    echo "✅ .env file already exists"
fi

# Build and start services
echo "🏗️  Building Docker images..."
docker-compose -f docker-compose.dev.yml build

echo "🚀 Starting development services..."
docker-compose -f docker-compose.dev.yml up -d

echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Application is healthy and running at http://localhost:8000"
else
    echo "❌ Application health check failed"
    echo "Check logs with: docker-compose -f docker-compose.dev.yml logs app"
fi

echo ""
echo "🎉 Development environment is ready!"
echo ""
echo "📋 Available services:"
echo "   - Application: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Redis: localhost:6379"
echo "   - Ollama: localhost:11434"
echo ""
echo "🔧 Useful commands:"
echo "   - View logs: docker-compose -f docker-compose.dev.yml logs -f"
echo "   - Stop services: docker-compose -f docker-compose.dev.yml down"
echo "   - Restart app: docker-compose -f docker-compose.dev.yml restart app"
echo "   - Run tests: docker-compose -f docker-compose.dev.yml exec app pytest"
echo ""
echo "🧪 Test Ollama connection:"
echo "   curl -X POST 'http://localhost:8000/api/v1/extract' -H 'Content-Type: application/json' -d '{\"text\":\"test document\"}'"
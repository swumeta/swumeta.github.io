# Makefile to launch an HTTP server
# Usage: make serve [PORT=8000] [DIR=public]

# Default values
PORT ?= 8000
DIR ?= public

.PHONY: serve help

# Main target to launch the HTTP server
serve:
	@echo "Starting HTTP server on port $(PORT) from directory $(DIR)"
	@echo "Access URL: http://localhost:$(PORT)"
	@echo "Press Ctrl+C to stop the server"
	@python -m http.server $(PORT) -d $(DIR)

# Help target to display available commands
help:
	@echo "Available targets:"
	@echo "  serve     - Launch a local HTTP server"
	@echo ""
	@echo "Options:"
	@echo "  PORT=xxxx - Specify the port (default: 8000)"
	@echo "  DIR=path  - Specify the root directory (default: public)"
	@echo ""
	@echo "Example:"
	@echo "  make serve PORT=3000 DIR=./public"

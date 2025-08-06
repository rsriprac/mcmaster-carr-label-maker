# McMaster-Carr Label Generator Makefile

.PHONY: test test-unit test-integration test-edge test-coverage clean install help

# Default target
help:
	@echo "McMaster-Carr Label Generator Test Commands:"
	@echo ""
	@echo "make test              - Run all tests with coverage"
	@echo "make test-unit         - Run only unit tests"
	@echo "make test-integration  - Run only integration tests"
	@echo "make test-edge         - Run only edge case tests"
	@echo "make test-coverage     - Run tests and open coverage report"
	@echo "make install           - Install dependencies"
	@echo "make clean             - Clean up generated files"
	@echo "make labels            - Generate sample labels using cached data"

# Install dependencies
install:
	pip install -r requirements.txt

# Run all tests
test:
	python run_tests.py

# Run specific test categories
test-unit:
	python -m pytest tests/test_label_generator.py tests/test_image_processor.py -v

test-integration:
	python -m pytest tests/test_integration.py -v

test-edge:
	python -m pytest tests/test_edge_cases.py -v

# Run tests and open coverage report
test-coverage: test
	@echo "Opening coverage report..."
	@if command -v open >/dev/null 2>&1; then \
		open htmlcov/index.html; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open htmlcov/index.html; \
	else \
		echo "Please open htmlcov/index.html in your browser"; \
	fi

# Generate sample labels
labels:
	python -m src.main 91290A115 91290A116 91290A117 --output sample_labels.pdf

# Clean up generated files
clean:
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf **/__pycache__/
	rm -rf **/*.pyc
	rm -f .coverage
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
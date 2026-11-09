#!/bin/bash

# Set up variables
REPO_DIR=$(pwd)
SITE_DIR="_site"
DOCS_DIR="docs"

# Render the Quarto project
echo "Rendering Quarto project..."
quarto render

# Check if rendering was successful
if [ $? -ne 0 ]; then
    echo "Error: Quarto render failed."
    exit 1
fi

# Create the docs folder if it doesn't exist
echo "Creating 'docs' folder..."
mkdir -p $DOCS_DIR

# Move the rendered files from _site to docs/
echo "Copying rendered files to 'docs' folder..."
cp -r $SITE_DIR/* $DOCS_DIR/
touch $DOCS_DIR/.nojekyll  # serve files as-is, skip Jekyll

# Add the changes to git
echo "Adding changes to Git..."
git add $DOCS_DIR

# Commit the changes
echo "Committing changes..."
git commit -m "Deploy Quarto dashboard to GitHub Pages"

# Push the changes to GitHub
echo "Pushing changes to GitHub..."
git push

# Output the GitHub Pages URL
echo "GitHub Pages site is now live at:"
echo "https://snfagora.github.io/agora_dashboard/"

# End of script

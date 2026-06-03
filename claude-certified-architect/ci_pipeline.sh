name: Claude PR Review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Load prior review findings # ← dedup
        run: |
          gh pr view ${{ github.event.pull_request.number }} \
            --json comments --jq '...' > prior_findings.txt

      - name: Run Claude review # ← fresh session, -p flag
        run: |
          PRIOR=$(cat prior_findings.txt)
          claude -p "Review the PR. Existing issues (skip): ${PRIOR}" \
            --output-format json \                  # ← structured output
            --json-schema .claude/review_schema.json \
            > findings.json
            # CLAUDE.md loaded automatically ↑

      - name: Block merge on critical findings
        run: |
          CRITICAL=$(jq '.findings | map(select(.severity=="critical")) | length' findings.json)
          [ "$CRITICAL" -eq 0 ] || exit 1
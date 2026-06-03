const batchRequests = changedFiles.map(file => ({
  custom_id: `review-${file.path}-${file.commitSha}`,
  params: {
    model: "claude-sonnet-4-20250514",
    max_tokens: 2048,
    messages: [{
      role: "user",
      content: `Review this file for issues:\n${file.content}`
    }]
  }
}));

// When results come back, each has the same custom_id
for (const result of batchResults) {
  const fileId = result.custom_id;  // "review-src/auth.ts-abc123"
  const review = result.result.message.content;
  saveReview(fileId, review);
}
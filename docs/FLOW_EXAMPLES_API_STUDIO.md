# Flow Examples – Clockify API Studio

Example 1: Auto-tag time entries for a specific project
- Trigger: TIME_ENTRY_CREATED
- Condition: payload.projectId == "PROJECT_X"
- Action: update time entry to add TAG_BILLABLE.

Example 2: Enforce non-empty descriptions
- Trigger: TIME_ENTRY_CREATED, TIME_ENTRY_UPDATED
- Condition: payload.description is null/empty
- Action: update time entry with default description string.

Example 3: Multi-step flow
- Action 1: GET user by payload.userId.
- Action 2: Update time entry tags based on GET user response.

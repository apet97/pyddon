# Clockify Marketplace Notes

This document provides important information for marketplace reviewers and administrators about this addon's behavior, permissions, and data handling.

## Overview

The Clockify Python Addon Boilerplate is a production-ready foundation for building Clockify integrations with:
- Full lifecycle management (install, update, delete)
- Comprehensive webhook event handling
- No-code API explorer powered by OpenAPI
- Automatic workspace data bootstrap
- Secure JWT/JWKS-based authentication

## Webhook Event Subscriptions

This addon subscribes to the following Clockify webhook events:

### Time Entry Events
- `NEW_TIME_ENTRY` - When a new time entry is created
- `TIME_ENTRY_UPDATED` - When a time entry is modified
- `TIME_ENTRY_DELETED` - When a time entry is deleted
- `TIME_ENTRY_RESTORED` - When a deleted time entry is restored
- `TIME_ENTRY_SPLIT` - When a time entry is split into multiple entries
- `TIME_ENTRY_BATCH_DELETED` - When multiple time entries are deleted at once
- `NEW_TIMER_STARTED` - When a timer is started
- `TIMER_STOPPED` - When a running timer is stopped

### Project Events
- `NEW_PROJECT` - When a new project is created
- `PROJECT_UPDATED` - When a project is modified
- `PROJECT_DELETED` - When a project is deleted

### User Events
- `USER_UPDATED` - When user profile information changes
- `USER_ACTIVATED_ON_WORKSPACE` - When a user is activated
- `USER_DEACTIVATED_ON_WORKSPACE` - When a user is deactivated
- `USER_DELETED_FROM_WORKSPACE` - When a user is removed
- `USER_JOINED_WORKSPACE` - When a new user joins
- `USER_EMAIL_CHANGED` - When a user's email address changes

### Expense Events
- `EXPENSE_CREATED` - When a new expense is created
- `EXPENSE_UPDATED` - When an expense is modified
- `EXPENSE_DELETED` - When an expense is deleted
- `EXPENSE_RESTORED` - When a deleted expense is restored

### Client, Tag, and Task Events
- `NEW_CLIENT`, `CLIENT_UPDATED`, `CLIENT_DELETED`
- `NEW_TAG`, `TAG_UPDATED`, `TAG_DELETED`
- `NEW_TASK`, `TASK_UPDATED`, `TASK_DELETED`

### Assignment Events (Scheduling)
- `ASSIGNMENT_CREATED` - When a user is assigned to a project
- `ASSIGNMENT_UPDATED` - When an assignment is modified
- `ASSIGNMENT_DELETED` - When an assignment is removed
- `ASSIGNMENT_PUBLISHED` - When an assignment is published

### Approval Events
- `APPROVAL_REQUEST_STATUS_UPDATED` - When approval status changes
- `NEW_APPROVAL_REQUEST` - When a new approval request is created

## Requested Permissions (Scopes)

### Read Permissions
- `WORKSPACE_READ` - Read workspace settings and configuration
- `USER_READ` - Read user profiles and workspace members
- `TIME_ENTRY_READ` - Read time entries
- `PROJECT_READ` - Read projects and related data
- `CLIENT_READ` - Read client information
- `TAG_READ` - Read tags
- `TASK_READ` - Read tasks
- `CUSTOM_FIELD_READ` - Read custom field definitions
- `EXPENSE_READ` - Read expense data
- `REPORT_READ` - Access reporting data
- `TIMEOFF_READ` - Read time-off requests and balances
- `APPROVAL_READ` - Read approval requests

### Write Permissions
- `TIME_ENTRY_WRITE` - Create, update, and delete time entries
- `PROJECT_WRITE` - Create, update, and delete projects
- `CLIENT_WRITE` - Create, update, and delete clients
- `TAG_WRITE` - Create, update, and delete tags
- `TASK_WRITE` - Create, update, and delete tasks
- `CUSTOM_FIELD_WRITE` - Manage custom field definitions
- `EXPENSE_WRITE` - Create, update, and delete expenses

### Justification for Permissions

**Read Permissions**: Required for the bootstrap functionality, which fetches and caches workspace data to provide context for the addon's operations. Also used by the no-code API explorer.

**Write Permissions**: Enables the no-code API caller to perform full CRUD operations on workspace entities as requested by users through the UI.

**Not Requested**: 
- `WORKSPACE_WRITE` - Not needed; addon doesn't modify workspace settings
- `USER_WRITE` - Not needed; addon doesn't modify user accounts
- `INVOICE_*` - Not needed for core functionality
- `WEBHOOK_*` - Not needed; addon doesn't manage webhook subscriptions
- `SCHEDULING_WRITE` - Limited to read-only access for assignments
- `TIMEOFF_WRITE` - Limited to read-only access
- `APPROVAL_WRITE` - Limited to read-only access

## Data Storage and Retention

### What Data is Stored

1. **Installation Records**
   - Workspace ID
   - Addon ID
   - Addon token (encrypted in transit, stored securely)
   - API URL
   - Installation status
   - User-configured settings
   - Timestamps (created, updated, deleted)

2. **Webhook Events**
   - Event ID (for deduplication)
   - Workspace ID
   - Event type
   - Full event payload
   - Metadata (headers, timestamps)
   - Processing status

3. **API Call Logs**
   - Workspace ID
   - Endpoint and HTTP method
   - Request parameters and body
   - Response status and body
   - Error messages (if any)
   - Duration and timestamps

4. **Bootstrap Data**
   - Workspace entities (projects, clients, tags, tasks, users, etc.)
   - Fetched via safe GET endpoints
   - Cached for addon functionality
   - Source endpoint information
   - Fetch timestamps

5. **Bootstrap Job Status**
   - Job progress and completion status
   - Success/failure counts
   - Error messages

### Data Retention Policy

- **Installation Records**: Retained indefinitely; soft-deleted on uninstall
- **Webhook Events**: Retained for 90 days by default (configurable)
- **API Call Logs**: Retained for 30 days by default (configurable)
- **Bootstrap Data**: Refreshed on each bootstrap run; old data replaced
- **Bootstrap Jobs**: Retained for 7 days by default (configurable)

### Data Location

- All data is stored in the addon's database (configured via `DATABASE_URL`)
- Default: Local SQLite (development)
- Recommended: PostgreSQL (production)
- No data is transmitted to third parties
- No data leaves the hosting infrastructure

## Uninstall Behavior (`/lifecycle/deleted`)

When a workspace uninstalls the addon:

1. **Installation Record**: Status set to `DELETED`, `deleted_at` timestamp recorded
2. **Addon Token**: Marked as revoked (stored for audit purposes)
3. **Webhook Events**: Preserved for compliance/audit (if required)
4. **API Call Logs**: Preserved for compliance/audit (if required)
5. **Bootstrap Data**: Can be purged (configurable)
6. **No External Callbacks**: Addon does not notify external systems
7. **Data Anonymization**: Optional purge of PII after retention period

### Hard Delete Option

For complete data removal, implement a scheduled job that:
- Identifies installations deleted > 90 days ago
- Permanently removes all associated records
- Logs deletion actions for compliance

Example implementation available in documentation.

## Security Measures

### Authentication
- **JWT/JWKS Verification**: All lifecycle and webhook requests verified using RS256 signatures
- **Workspace Isolation**: Claims validated against payload to prevent cross-workspace access
- **Addon ID Validation**: Ensures requests are intended for this addon
- **Developer Mode Bypass**: Signature verification can be disabled for local development only

### Rate Limiting
- Token bucket algorithm: 50 RPS per workspace (configurable)
- Prevents API abuse and respects Clockify rate limits
- Redis-based distributed limiting for multi-instance deployments

### Deduplication
- Webhook events deduplicated by event ID
- Database-backed persistence (survives restarts)
- Memory cache for performance
- Prevents double-processing of events

### Data Protection
- Addon tokens stored securely
- Sensitive data never logged
- HTTPS required for production deployments
- Regular security audits recommended

## Compliance and Privacy

### GDPR Compliance
- Users can request data export (implement via custom endpoint)
- Data deletion on uninstall (soft or hard delete)
- Audit logs for data access
- No data shared with third parties

### Data Processing
- **Purpose**: Enable addon functionality and workspace synchronization
- **Legal Basis**: Consent (via addon installation)
- **Data Controller**: Workspace administrator
- **Data Processor**: Addon operator

### User Rights
- Right to access stored data
- Right to deletion (uninstall)
- Right to data portability
- Right to rectification

## Support and Monitoring

### Logging
- Structured JSON logs (production)
- Sensitive data redacted
- Error tracking and alerting
- Performance metrics

### Health Checks
- `/health` endpoint for monitoring
- Database connectivity check
- API availability check

### Support Channels
- Support email: `support@your-company.com`
- Documentation: Available at base URL + `/docs`
- Issue tracking: GitHub Issues (if open source)

## Known Limitations

1. **Bootstrap Limitations**
   - Only fetches GET endpoints with `{workspaceId}` parameter
   - Does not fetch entity-specific details (requires IDs)
   - Pagination limited to 10 pages per endpoint
   - Rate-limited to prevent API quota exhaustion

2. **Rate Limiting**
   - Per-process limitation (use Redis for distributed systems)
   - No cross-workspace rate limiting
   - No user-level rate limiting

3. **Deduplication**
   - Memory cache limited by TTL (1 hour)
   - Database unique constraint as fallback
   - No distributed cache without Redis

4. **Webhook Processing**
   - Synchronous processing (may need async queue for high volume)
   - No retry mechanism for failed processing
   - No dead-letter queue

## Production Deployment Checklist

- [ ] Set `REQUIRE_SIGNATURE_VERIFICATION=true`
- [ ] Use PostgreSQL database
- [ ] Enable Redis for rate limiting
- [ ] Configure proper `BASE_URL` with HTTPS
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation
- [ ] Implement data retention policies
- [ ] Set up backup and disaster recovery
- [ ] Review and minimize requested scopes
- [ ] Update vendor information in manifest
- [ ] Add privacy policy and terms of service URLs
- [ ] Test installation, update, and deletion flows
- [ ] Verify webhook event handling
- [ ] Load test API endpoints
- [ ] Security audit and penetration testing
- [ ] Document any workspace-specific configuration

## Marketplace Approval Requirements

### Technical Requirements
✅ Manifest schema version 1.3
✅ Explicit webhook event subscriptions
✅ Minimal required scopes
✅ Proper lifecycle event handling
✅ Secure authentication (RS256 JWT)
✅ Rate limiting implemented
✅ Error handling and logging
✅ Health check endpoint

### Documentation Requirements
✅ README with setup instructions
✅ Environment variable documentation
✅ API documentation
✅ Privacy policy URL
✅ Terms of service URL
✅ Support contact information

### Security Requirements
✅ No hardcoded secrets
✅ HTTPS for production
✅ Input validation
✅ Output encoding
✅ SQL injection prevention (ORM)
✅ XSS prevention
✅ CSRF protection (where applicable)

### Quality Requirements
✅ Automated tests
✅ Code linting
✅ Structured logging
✅ Performance optimization
✅ Graceful error handling
✅ Database migrations

## Contact Information

- **Vendor**: Your Company
- **Support Email**: support@your-company.com
- **Website**: https://your-company.com
- **Documentation**: https://your-company.com/clockify-addon/docs
- **Privacy Policy**: https://your-company.com/privacy
- **Terms of Service**: https://your-company.com/terms

---

**Last Updated**: 2024-11-14
**Addon Version**: 1.0.0
**Manifest Schema**: 1.3

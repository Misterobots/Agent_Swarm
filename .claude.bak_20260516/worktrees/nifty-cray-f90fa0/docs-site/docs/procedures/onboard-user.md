---
title: "Procedure: Onboard User"
---

# Onboard a User

Set up a new user with access to Memex.

## Steps

### 1. Provide Access URL

Give the user the Hive UI URL:

- **LAN**: `http://{{ turing_ip }}/`
- **Remote**: Share Tailscale URL

### 2. Create Owner ID

Assign a unique `owner_id` for the user. This is used to scope:

- Session history
- Skills Memory rules
- Training data
- Preferences

### 3. Orient the User

Share these documentation pages:

1. [Getting Started: User Quickstart](../getting-started/quickstart-user.md)
2. [User Guide: Chat](../user-guide/chat.md)
3. [User Guide: Settings](../user-guide/settings.md)

### 4. Set Initial Preferences

The user can teach preferences via chat:

> "Remember that I prefer detailed code comments"
> "I like responses in bullet point format"

These are stored in Skills Memory under their `owner_id`.

### 5. Verify Access

Have the user send a test message through the Hive UI to confirm end-to-end functionality.



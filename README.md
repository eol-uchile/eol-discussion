# Eol Xblock Discussion

![Coverage Status](/coverage-badge.svg)

![https://github.com/eol-uchile/eol-discussion/actions](https://github.com/eol-uchile/eol-discussion/workflows/Python%20application/badge.svg)


# Install App
```
docker-compose exec cms pip install -e /openedx/requirements/eoldiscussion && docker-compose exec lms pip install -e /openedx/requirements/eoldiscussion
```

# Configuration

Edit *production.py* in *lms and cms settings* and set the limit_thread, this parameter configures the maximum number of publications that are obtained from a discussion.

    EOLGRADEFORUM_LIMIT_THREADS = 5000
    CORS_ALLOW_CREDENTIALS = True
    CORS_ORIGIN_WHITELIST = ['studio.domain.com']
    CORS_ALLOW_HEADERS = corsheaders_default_headers + (
        'use-jwt-cookie',
    )

## TESTS

**Prepare tests:**

- Install **act** following the instructions in [https://nektosact.com/installation/index.html](https://nektosact.com/installation/index.html)

**Run tests:**
- In a terminal at the root of the project
    ```
    act -W .github/workflows/pythonapp.yml
    ```

# Eol Xblock Discussion

![Coverage Status](/coverage-badge.svg)

Copy templates/eoldiscussion to your custom theme in custom_theme/lms/templates

# Install App
```
docker-compose exec cms pip install -e /openedx/requirements/eoldiscussion && docker-compose exec lms pip install -e /openedx/requirements/eoldiscussion
```

## TESTS
**Prepare tests:**

- Install **act** following the instructions in [https://nektosact.com/installation/index.html](https://nektosact.com/installation/index.html)

**Run tests:**
- In a terminal at the root of the project
    ```
    act -W .github/workflows/pythonapp.yml
    ```

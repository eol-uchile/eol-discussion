Use this translations directory to provide internationalized strings for your XBlock project.

In project root directory, execute
```
docker run -it --rm -w /code -v $(pwd):/code python:3.8 bash
pip install -r requirements-i18n.in
make update_translations
make compile_translations
```

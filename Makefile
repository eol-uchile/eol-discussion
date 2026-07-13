.DEFAULT_GOAL := help
.PHONY: requirements

# include *.mk

# Generates a help message. Borrowed from https://github.com/pydanny/cookiecutter-djangopackage.
help: ## Display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@perl -nle'print $& if m{^[\.a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m %-25s\033[0m %s\n", $$1, $$2}'

lang_targets = en es_419
create_translations_catalogs: ## Create the initial configuration of .mo files for translation
	pybabel extract -F eoldiscussion/locale/babel.cfg -o eoldiscussion/locale/django.pot --msgid-bugs-address=eol-ing@uchile.cl --copyright-holder=EOL --project=EOL --version=1.0.0 --last-translator='EOL <eol-ing@uchile.cl>' *
	pybabel extract -F eoldiscussion/locale/babel-js.cfg -o eoldiscussion/locale/django-js.pot --msgid-bugs-address=eol-ing@uchile.cl --copyright-holder=EOL --project=EOL --version=1.0.0 --last-translator='EOL <eol-ing@uchile.cl>' *
	for lang in $(lang_targets) ; do \
		pybabel init -i eoldiscussion/locale/django.pot -D django -d eoldiscussion/locale/ -l $$lang ; \
		pybabel init -i eoldiscussion/locale/django-js.pot -D djangojs -d eoldiscussion/locale/ -l $$lang ; \
	done

update_translations: ## update strings to be translated
	pybabel extract -F eoldiscussion/locale/babel.cfg -o eoldiscussion/locale/django.pot --msgid-bugs-address=eol-ing@uchile.cl --copyright-holder=EOL --project=EOL --version=1.0.0 --last-translator='EOL <eol-ing@uchile.cl>' * 
	pybabel extract -F eoldiscussion/locale/babel-js.cfg -o eoldiscussion/locale/django-js.pot --msgid-bugs-address=eol-ing@uchile.cl --copyright-holder=EOL --project=EOL --version=1.0.0 --last-translator='EOL <eol-ing@uchile.cl>' *
	pybabel update -N -D django -i eoldiscussion/locale/django.pot -d eoldiscussion/locale/
	pybabel update -N -D djangojs -i eoldiscussion/locale/django-js.pot -d eoldiscussion/locale/
	rm eoldiscussion/locale/django.pot
	rm eoldiscussion/locale/django-js.pot

compile_translations: ## compile .mo files into .po files
	pybabel compile -f -D django -d eoldiscussion/locale/; \
	pybabel compile -f -D djangojs -d eoldiscussion/locale/

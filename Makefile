run:
	@echo Starting server at port 8000 ...
	python3 manage.py runserver

migrations:
	@echo Making migrations ...
	python3 manage.py migrate
	python3 manage.py makemigrations
	python3 manage.py migrate

superuser:
	@echo creating superuser ...
	python3 manage.py createsuperuser
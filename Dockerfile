FROM continuumio/miniconda3

WORKDIR /app

# Create the environment:
COPY environment.yml .
RUN conda env create -f environment.yml

# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "dash1_env", "/bin/bash", "-c"]

# Environment variables for the app.
ENV DB_LOGIN='admin'
ENV DB_PWORD='Exodu$18'
ENV MAPBOX_TOKEN='pk.eyJ1IjoidHlhcm9zZXZpY2giLCJhIjoiY2tqbHlsejF3MDRwbzJ5bXVxY2d5cDlsbyJ9.zBWyx6rzTIo6Uw_w1Iu-AA'
	
ADD . $DB_LOGIN
ADD . $DB_PWORD
ADD . $MAPBOX_TOKEN

# The code to run when container is started:
COPY application.py .
COPY utils.py .
COPY assets/ /app/assets/
COPY static/ /app/static/
EXPOSE 8080
ENTRYPOINT ["conda", "run", "-n", "dash1_env", "python", "application.py"]


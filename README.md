For exec, the app container must already be running, so the sequence is:

docker compose -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml exec app python -m src.simulation.auto_simulate --interval 10 --count 5 --mode new
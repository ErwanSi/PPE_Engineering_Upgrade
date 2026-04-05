import redis

# Connexion
r = redis.Redis(host='localhost', port=6379, db=0)

# Nettoyage
r.flushall()

print("🧹 Base Redis vidée avec succès.")
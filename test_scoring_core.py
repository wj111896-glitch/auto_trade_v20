from scoring.core import ScoreEngine
from scoring.weights import Weights

engine = ScoreEngine(Weights())
score = engine.evaluate({"dummy":"data"})
print("score:", score)

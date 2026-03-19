"""Script placeholder pour l'import du modèle via MLflow."""

from pathlib import Path


MODEL_DIR = Path("model/imported_model")
MODEL_METADATA_PATH = Path("model/model_metadata.json")


def main() -> None:
    print(f"Répertoire cible du modèle : {MODEL_DIR}")
    print(f"Fichier cible des métadonnées : {MODEL_METADATA_PATH}")
    print("Implémentation de l'import MLflow à venir.")


if __name__ == "__main__":
    main()

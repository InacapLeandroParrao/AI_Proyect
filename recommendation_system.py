"""Sistema de recomendacion sencillo basado en K vecinos mas cercanos."""

# Importar las librerías necesarias
from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["action", "comedy", "drama", "runtime_minutes"]
TARGET = "category"
ITEM_NAME = "title"

# Cargar los datos
SAMPLE_DATA = """title,action,comedy,drama,runtime_minutes,category
Sky Frontier,5,1,1,128,Adventure
The Last Summit,5,1,2,142,Adventure
Jungle Signal,4,1,1,116,Adventure
Orbit Rescue,5,2,1,131,Adventure
Desert Compass,4,1,2,123,Adventure
Weekend Mix-Up,1,5,1,102,Comedy
The Office Picnic,1,5,1,96,Comedy
Laughing Matters,2,5,1,110,Comedy
Roommates Again,1,4,2,105,Comedy
The Big Reunion,1,5,2,114,Comedy
Quiet Harbor,1,1,5,124,Drama
Letters in Winter,1,1,5,117,Drama
The Long Goodbye,2,1,5,139,Drama
Small Town Echoes,1,2,4,108,Drama
After the Rain,1,1,5,132,Drama
"""

def load_data(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Carga el catalogo de ejemplo o un archivo CSV con el mismo esquema."""
    if csv_path is None:
        data = pd.read_csv(StringIO(SAMPLE_DATA))
    else:
        data = pd.read_csv(csv_path)

    required_columns = {ITEM_NAME, TARGET, *FEATURES}
    missing_columns = required_columns.difference(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Faltan columnas requeridas en el CSV: {missing}")
    if data.empty:
        raise ValueError("El catalogo no puede estar vacio.")

    data = data.dropna(subset=[ITEM_NAME, TARGET]).reset_index(drop=True)
    for feature in FEATURES:
        data[feature] = pd.to_numeric(data[feature], errors="raise")
    if data.empty:
        raise ValueError("El catalogo no contiene filas completas.")
    return data

# Preprocesamiento de datos
def _make_preprocessor() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

def train_and_evaluate(
    data: pd.DataFrame,
    n_neighbors: int = 3,
    test_size: float = 0.25,
    random_state: int = 42,
) -> tuple[KNeighborsClassifier, Pipeline, float]:
    """Evalua el clasificador y lo ajusta despues con todo el catalogo."""
    if n_neighbors < 1:
        raise ValueError("n_neighbors debe ser al menos 1.")

    features = data[FEATURES]
    labels = data[TARGET]

    # Dividir los datos en entrenamiento y prueba
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=test_size,
        random_state=random_state,
        stratify=labels,
    )
    if n_neighbors > len(x_train):
        raise ValueError(
            "n_neighbors no puede ser mayor que el numero de filas de entrenamiento."
        )

    # Crear y entrenar el modelo
    evaluation_preprocessor = _make_preprocessor()
    x_train_scaled = evaluation_preprocessor.fit_transform(x_train)
    x_test_scaled = evaluation_preprocessor.transform(x_test)
    evaluation_model = KNeighborsClassifier(n_neighbors=n_neighbors)
    evaluation_model.fit(x_train_scaled, y_train)

    # Realizar predicciones
    predictions = evaluation_model.predict(x_test_scaled)

    # Evaluar el modelo
    accuracy = accuracy_score(y_test, predictions)

    preprocessor = _make_preprocessor()
    all_features_scaled = preprocessor.fit_transform(features)
    model = KNeighborsClassifier(n_neighbors=n_neighbors)
    model.fit(all_features_scaled, labels)
    return model, preprocessor, float(accuracy)

# Función de recomendación
def recommend(
    preferences: dict[str, float],
    data: pd.DataFrame,
    model: KNeighborsClassifier,
    preprocessor: Pipeline,
    k: int = 5,
) -> pd.DataFrame:
    """Devuelve los k elementos mas cercanos a las preferencias indicadas."""
    if k < 1:
        raise ValueError("k debe ser al menos 1.")
    missing_features = set(FEATURES).difference(preferences)
    if missing_features:
        missing = ", ".join(sorted(missing_features))
        raise ValueError(f"Faltan preferencias para estas caracteristicas: {missing}")
    if len(data) < k:
        raise ValueError("k no puede ser mayor que el numero de elementos del catalogo.")

    preference_row = pd.DataFrame(
        [{feature: preferences[feature] for feature in FEATURES}]
    )
    for feature in FEATURES:
        preference_row[feature] = pd.to_numeric(
            preference_row[feature], errors="raise"
        )

    scaled_preferences = preprocessor.transform(preference_row)
    distances, indices = model.kneighbors(scaled_preferences, n_neighbors=k)
    recommendations = data.iloc[indices[0]][[ITEM_NAME, TARGET]].reset_index(drop=True)
    recommendations["distance"] = distances[0]
    return recommendations

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Entrena un recomendador KNN a partir de un catalogo CSV."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        help="Ruta al CSV (si se omite, se utiliza el catalogo de ejemplo).",
    )
    parser.add_argument(
        "--neighbors",
        type=int,
        default=3,
        help="Numero de vecinos del clasificador (por defecto: 3).",
    )
    args = parser.parse_args()

    data = load_data(args.csv_path)
    model, preprocessor, accuracy = train_and_evaluate(
        data, n_neighbors=args.neighbors
    )
    print(f"Precision (accuracy): {accuracy:.2%}")
    preferences = {
        "action": 5,
        "comedy": 1,
        "drama": 1,
        "runtime_minutes": 125,
    }
    print("\nRecomendaciones:")
    print(recommend(preferences, data, model, preprocessor).to_string(index=False))


if __name__ == "__main__":
    main()
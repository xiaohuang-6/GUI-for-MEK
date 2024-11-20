# Electron Bifurcation & Hole Bifurcation Design Visualization Tool

This project provides a Python-based GUI for **visualizing and optimizing parameters** related to electron and hole bifurcation design. It incorporates **Bayesian Optimization** to find optimal parameter configurations for maximizing final yields under specific physical constraints.

---

## Features

- **Interactive Sliders**: Dynamically adjust parameters like energy levels, distances, and reorganization energy.
- **Bayesian Optimization**: Automate the process of finding optimal parameter configurations for maximum yield.
- **Real-Time Visualizations**: Energy landscapes and efficiency metrics are updated live with parameter changes.
- **Constraint Enforcement**: Ensure physically valid parameters, such as:
  - $ G_6 \leq G_1 $
  - $ G_6 < G_7 $
- **Customizable Codebase**: Modify the optimization criteria and constraints according to research needs.

---

## Installation

### Prerequisites
- Python 3.8 or higher
- Required Python packages (install using pip):
    ```bash
    pip install -r requirements.txt
    ```

### Steps to Run
1. Clone this repository:
    ```bash
    git clone https://github.com/your-repo-name/electron-bifurcation-gui.git
    cd electron-bifurcation-gui
    ```
2. Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3. Run the GUI:
    ```bash
    python GUI.py
    ```

---

## GUI Overview

### Parameter Sliders
- Modify key parameters interactively:
  - **Energy Levels (G1, G2, ..., G7)**: Energy (in eV) of cofactors.
  - **Distances (distance_H, distance_L, distance)**: Edge-to-edge distances (in Å).
  - **Reorganization Energy (reorgE)**: Electron transfer reorganization energy (in eV).

### Visualization
- **Energy Landscape**: Displays orbital energy as a function of cofactor distance.
- **Text Metrics**: Displays probabilities, energy efficiencies, and total efficiency.

### Optimization
- Clicking **"Generate the best parameters"** applies Bayesian Optimization to maximize the final yield while maintaining constraints.

---

## Code Structure

- **`hole_transfer` Function**: Simulates bifurcation using the `Network` object, computing final yield, probabilities, and total efficiency.
- **`function_to_optimize` Function**: Defines the optimization objective for Bayesian Optimization.
- **`generate_best_parameters` Function**: Applies optimization and updates GUI sliders and plots.
- **`update_plot` Function**: Updates visualization plots and textual outputs dynamically.

---

## Parameter Constraints

The model enforces constraints to ensure physical validity:
- **Energy Levels**:
  - \( G_6 \leq G_1 \)
  - \( G_6 < G_7 \)
- **Distance Bounds**:
  - \( \text{distance}_H, \text{distance}_L, \text{distance} \in [5, 15] \) (Å)
- **Reorganization Energy**:
  - \( \text{reorgE} \in [0.7, 0.8] \) (eV)

---

## Example Outputs

### GUI Example
![GUI Example](images/gui_interface.png)

### Energy Landscape Plot
![Energy Landscape](images/energy_landscape.png)

---

## How to Contribute

We welcome contributions! Here's how you can help:
1. Fork the repository.
2. Create a new branch (`feature/new-feature`).
3. Submit a pull request with a detailed explanation.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Contact

For questions or feedback, reach out:
- **Name**: [Your Name]
- **Email**: your.email@example.com
- **GitHub**: [your-github-handle](https://github.com/your-github-handle)

---
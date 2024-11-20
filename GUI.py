import tkinter as tk
from tkinter import messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.gridspec as gridspec
from bayes_opt import BayesianOptimization
import numpy as np

from MEK_vib import Network, Cofactor

# Parameters
time = 1  # s
canvas = None

# Function to handle hole transfer simulation
def hole_transfer(G1, G2, G3, G4, G5, G6, G7, distance_H, distance_L, distance, reorgE):
    net = Network()
    # Add cofactors
    E = Cofactor("E", [G1, 0])
    H1 = Cofactor("H1", [G2])
    L1 = Cofactor("L1", [G3])
    H2 = Cofactor("H2", [G4])
    L2 = Cofactor("L2", [G5])
    H3 = Cofactor("H3", [G6])
    L3 = Cofactor("L3", [G7])

    net.addCofactor(E)
    net.addCofactor(H1)
    net.addCofactor(L1)
    net.addCofactor(H2)
    net.addCofactor(L2)
    net.addCofactor(H3)
    net.addCofactor(L3)

    # Add connections
    # add connection (all combination), where E to L1 is distance_L, E to H1 is distance_H, and all other adjacent cofactors are distance, and from left to right is H3, H2, H1, E, L1, L2, L3
    net.addConnection(H3, H2, distance)
    net.addConnection(H3, H1, 2*distance)
    net.addConnection(H3, E, 2*distance+distance_H)
    net.addConnection(H3, L1, 2*distance+distance_H+distance_L)
    net.addConnection(H3, L2, 3*distance+distance_H+distance_L)
    net.addConnection(H3, L3, 4*distance+distance_H+distance_L)
    net.addConnection(H2, H1, distance)
    net.addConnection(H2, E, distance+distance_H)
    net.addConnection(H2, L1, distance+distance_H+distance_L)
    net.addConnection(H2, L2, 2*distance+distance_H+distance_L)
    net.addConnection(H2, L3, 3*distance+distance_H+distance_L)
    net.addConnection(H1, E, distance_H)
    net.addConnection(H1, L1, distance_H+distance_L)
    net.addConnection(H1, L2, distance+distance_H+distance_L)
    net.addConnection(H1, L3, 2*distance+distance_H+distance_L)
    net.addConnection(E, L1, distance_L)
    net.addConnection(E, L2, distance_L+distance)
    net.addConnection(E, L3, distance_L+2*distance)
    net.addConnection(L1, L2, distance)
    net.addConnection(L1, L3, 2*distance)
    net.addConnection(L2, L3, distance)

    # Set up the network
    net.set_Max_Electrons(6)
    net.set_Min_Electrons(6)
    net.constructStateList()
    net.constructAdjacencyMatrix()
    net.constructRateMatrix(reorgE)

    # Adjust rate matrix
    for j in range(0, len(net.K[0])):
        net.K[j][0] = 0
    for i in range(1, 6):
        for j in range(6, len(net.K[0])):
            net.K[j][i] = 0
    for i in range(6, 11):
        for j in range(11, len(net.K[0])):
            net.K[j][i] = 0
    # make net.K[j][j] sum of each j column but not sum the j=j element
    for j in range(0, len(net.K)):
        net.K[j][j] = -np.sum(net.K[:, j]) + net.K[j][j]

    # Initial population
    pop_init = np.zeros(net.adj_num_state)
    pop_init[21] = 1
    pop_MEK = net.evolve(time, pop_init)

    # Compute results
    final_yield = pop_MEK[0]
    max_prob = np.max(pop_MEK), np.argmax(pop_MEK)
    second_prob = sorted(pop_MEK)[-2], np.argsort(pop_MEK)[-2]
    energy_efficiency = 1 - (abs(G1 - G6) + abs(G7)) / abs(G1)
    total_efficiency = final_yield * energy_efficiency

    return final_yield, max_prob, second_prob, total_efficiency

# Bayesian optimization
def function_to_optimize(G1, G2, G3, G4, G5, G6, G7, distance_H, distance_L, distance, reorgE):
    if G6 > G1 or G6 >= G7:
        return -1000
    return hole_transfer(G1, G2, G3, G4, G5, G6, G7, distance_H, distance_L, distance, reorgE)[0]

def generate_best_parameters():
    pbounds = {
        'G1': (-1.9, -1.7), 'G2': (-4, -1.6), 'G3': (-0.8, -0.1), 'G4': (-4, -1.7),
        'G5': (-0.8, -0.1), 'G6': (-4, -1.8), 'G7': (-0.8, -0.1),
        'distance_H': (5, 15), 'distance_L': (5, 15), 'distance': (5, 15), 'reorgE': (0.7, 0.8)
    }
    optimizer = BayesianOptimization(function_to_optimize, pbounds, random_state=1)
    optimizer.maximize(init_points=2, n_iter=100)

    best_params = optimizer.max['params']
    print("Best parameters:", best_params)
    print("Best final_yield:", optimizer.max['target'])

    for param, value in best_params.items():
        sliders[param].set(value)

    update_plot()

def get_slider_values():
    return {param: slider.get() for param, slider in sliders.items()}

def update_plot():
    global canvas
    params = get_slider_values()
    target, max_prob, second_prob, total_efficiency = hole_transfer(
        params['G1'], params['G2'], params['G3'], params['G4'], params['G5'],
        params['G6'], params['G7'], params['distance_H'], params['distance_L'],
        params['distance'], params['reorgE']
    )

    # Plot setup
    gs = gridspec.GridSpec(2, 1, height_ratios=[4, 1.5])
    ax1 = plt.subplot(gs[0])
    ax2 = plt.subplot(gs[1])
    ax2.axis('off')

    # Plot energy landscape
    x = [1, 1+params['distance'], 1+2*params['distance'], 1+2*params['distance']+params['distance_H'],
         1+2*params['distance']+params['distance_H']+params['distance_L'], 1+3*params['distance']+params['distance_H']+params['distance_L']]
    y = [-params['G6'], -params['G4'], -params['G2'], -params['G1'], -params['G3'], -params['G5'], -params['G7']]
    ax1.plot(x, y, 'o-')
    ax1.set_xticks(x)
    ax1.set_xticklabels(['H3', 'H2', 'H1', 'E', 'L1', 'L2', 'L3'])
    ax1.set_ylabel("Orbital Energy (eV)")
    ax1.set_title("Energy Landscape")

    # Update text info
    info = [
        f"Target Yield: {target:.2f}", f"Max Prob: {max_prob[0]:.2f} (Microstate: {max_prob[1]})",
        f"Second Prob: {second_prob[0]:.2f} (Microstate: {second_prob[1]})",
        f"Efficiency: {total_efficiency:.2f}"
    ]
    ax2.text(0.5, 0.5, "\n".join(info), ha='center', va='center')

    # Refresh canvas
    if canvas:
        canvas.get_tk_widget().grid_forget()
    canvas = FigureCanvasTkAgg(plt.gcf(), master=window)
    canvas.get_tk_widget().grid(row=0, column=1)
    canvas.draw()

# GUI Setup
window = tk.Tk()
window.title("Electron Bifurcation Visualization")
slider_frame = tk.Frame(window)
slider_frame.grid(row=0, column=0, sticky='n')

params = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'distance_H', 'distance_L', 'distance', 'reorgE']
sliders = {}

for i, param in enumerate(params):
    frame = tk.Frame(slider_frame)
    frame.grid(row=i, column=0, padx=5, pady=5)
    tk.Label(frame, text=param).pack(side=tk.LEFT)
    slider = tk.Scale(frame, from_=-5, to=20, resolution=0.05, orient=tk.HORIZONTAL, length=300)
    slider.pack(side=tk.RIGHT)
    sliders[param] = slider
    slider.config(command=lambda _: update_plot())

tk.Button(slider_frame, text="Generate Best Parameters", command=generate_best_parameters).grid(row=len(params), column=0, pady=10)

window.mainloop()
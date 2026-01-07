"""
CST Geometry Visualizer
Plots 2D profiles and 3D shapes to verify geometry before VSP generation
"""
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import math


class CSTVisualizer:
    """Visualize CST geometry for verification"""

    @staticmethod
    def cst_class_function(psi, N1, N2):
        """CST class function"""
        return (psi ** N1) * ((1 - psi) ** N2)

    @staticmethod
    def cst_shape_function(psi, weights):
        """CST shape function using Bernstein polynomials"""
        n = len(weights) - 1
        S = 0
        for i in range(len(weights)):
            comb = math.factorial(n) / (math.factorial(i) * math.factorial(n - i))
            bernstein = comb * (psi ** i) * ((1 - psi) ** (n - i))
            S += weights[i] * bernstein
        return S

    @staticmethod
    def calculate_cst_radius(psi, N1, N2, weights, length):
        """Calculate radius at position psi"""
        if psi <= 0 or psi >= 1:
            return 0.0
        C = CSTVisualizer.cst_class_function(psi, N1, N2)
        S = CSTVisualizer.cst_shape_function(psi, weights)
        return C * S * length

    def plot_2d_profile(self, design_params, num_points=100, save_path=None):
        """
        Plot 2D side view and front view of the fuselage

        Parameters:
        -----------
        design_params : dict
            Design parameters (same format as geometry generator)
        num_points : int
            Number of points for smooth curve
        save_path : str
            If provided, save figure to this path
        """
        L = design_params["length"]
        N1 = design_params["n_nose"]
        N2 = design_params["n_tail"]
        W_w = design_params["width_weights"]
        H_w = design_params["height_weights"]

        # Generate psi values (skip endpoints to avoid zero)
        psi_values = np.linspace(0.001, 0.999, num_points)
        x_values = psi_values * L

        # Calculate width and height distributions
        widths = np.array([self.calculate_cst_radius(psi, N1, N2, W_w, L) * 2 for psi in psi_values])
        heights = np.array([self.calculate_cst_radius(psi, N1, N2, H_w, L) * 2 for psi in psi_values])

        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        # Plot 1: Side view (height profile)
        ax1.plot(x_values, heights / 2, 'b-', linewidth=2, label='Top')
        ax1.plot(x_values, -heights / 2, 'b-', linewidth=2, label='Bottom')
        ax1.fill_between(x_values, -heights / 2, heights / 2, alpha=0.3, color='blue')
        ax1.axhline(y=0, color='k', linestyle='--', linewidth=0.5)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlabel('Length (m)', fontsize=12)
        ax1.set_ylabel('Height (m)', fontsize=12)
        ax1.set_title(f'Side View - {design_params["name"]}', fontsize=14, fontweight='bold')
        ax1.set_aspect('equal')
        ax1.legend()

        # Plot 2: Top view (width profile)
        ax2.plot(x_values, widths / 2, 'r-', linewidth=2, label='Right')
        ax2.plot(x_values, -widths / 2, 'r-', linewidth=2, label='Left')
        ax2.fill_between(x_values, -widths / 2, widths / 2, alpha=0.3, color='red')
        ax2.axhline(y=0, color='k', linestyle='--', linewidth=0.5)
        ax2.grid(True, alpha=0.3)
        ax2.set_xlabel('Length (m)', fontsize=12)
        ax2.set_ylabel('Width (m)', fontsize=12)
        ax2.set_title(f'Top View - {design_params["name"]}', fontsize=14, fontweight='bold')
        ax2.set_aspect('equal')
        ax2.legend()

        # Add parameter info
        param_text = (f"N_nose={N1}, N_tail={N2}\n"
                     f"Super_M/N={design_params.get('super_m', 2.0)}\n"
                     f"Length={L}m")
        fig.text(0.5, 0.02, param_text, ha='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout(rect=[0, 0.05, 1, 1])

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"   💾 Saved 2D profile to: {save_path}")

        return fig

    def plot_3d_shape(self, design_params, num_sections=40, num_theta=36, save_path=None):
        """
        Plot 3D wireframe of the fuselage with super ellipse cross-sections

        Parameters:
        -----------
        design_params : dict
            Design parameters
        num_sections : int
            Number of longitudinal sections
        num_theta : int
            Number of points around each cross-section
        save_path : str
            If provided, save figure to this path
        """
        L = design_params["length"]
        N1 = design_params["n_nose"]
        N2 = design_params["n_tail"]
        W_w = design_params["width_weights"]
        H_w = design_params["height_weights"]
        super_n = design_params.get("super_n", 2.0)

        # Generate longitudinal positions
        psi_values = np.linspace(0, 1, num_sections)
        x_values = psi_values * L

        # Generate angular positions
        theta = np.linspace(0, 2 * np.pi, num_theta)

        # Prepare 3D data
        X = np.zeros((num_sections, num_theta))
        Y = np.zeros((num_sections, num_theta))
        Z = np.zeros((num_sections, num_theta))

        for i, psi in enumerate(psi_values):
            # Get semi-axes at this position
            if psi == 0 or psi == 1:
                # Tips are points
                a = 0.0
                b = 0.0
            else:
                a = self.calculate_cst_radius(psi, N1, N2, W_w, L)  # semi-width
                b = self.calculate_cst_radius(psi, N1, N2, H_w, L)  # semi-height

            # Generate super ellipse cross-section
            for j, t in enumerate(theta):
                # Super ellipse parametric equations
                # x = a * |cos(t)|^(2/n) * sign(cos(t))
                # y = b * |sin(t)|^(2/n) * sign(sin(t))
                exp = 2.0 / super_n
                y_coord = a * (np.abs(np.cos(t)) ** exp) * np.sign(np.cos(t))
                z_coord = b * (np.abs(np.sin(t)) ** exp) * np.sign(np.sin(t))

                X[i, j] = x_values[i]
                Y[i, j] = y_coord
                Z[i, j] = z_coord

        # Create 3D plot
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')

        # Plot wireframe
        ax.plot_wireframe(X, Y, Z, color='blue', alpha=0.6, linewidth=0.5)

        # Plot some longitudinal lines for clarity
        for j in range(0, num_theta, 4):
            ax.plot(X[:, j], Y[:, j], Z[:, j], 'b-', linewidth=1, alpha=0.8)

        # Plot some cross-sections
        for i in range(0, num_sections, 5):
            ax.plot(X[i, :], Y[i, :], Z[i, :], 'r-', linewidth=1.5, alpha=0.7)

        # Highlight shoulder position (40% of length)
        shoulder_idx = int(0.4 * num_sections)
        ax.plot(X[shoulder_idx, :], Y[shoulder_idx, :], Z[shoulder_idx, :],
                'g-', linewidth=2.5, alpha=0.9, label='Shoulder Position (40%)')

        # Set labels and title
        ax.set_xlabel('Length (m)', fontsize=12)
        ax.set_ylabel('Width (m)', fontsize=12)
        ax.set_zlabel('Height (m)', fontsize=12)
        ax.set_title(f'3D Shape - {design_params["name"]}', fontsize=14, fontweight='bold')

        # Set equal aspect ratio
        max_range = L / 2
        ax.set_xlim([0, L])
        ax.set_ylim([-max_range, max_range])
        ax.set_zlim([-max_range, max_range])

        ax.legend()

        # Add parameter info
        param_text = (f"N_nose={N1}, N_tail={N2}, Super_N={super_n}\n"
                     f"Length={L}m, Sections={num_sections}")
        fig.text(0.5, 0.02, param_text, ha='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"   💾 Saved 3D shape to: {save_path}")

        return fig

    def create_comparison_plot(self, designs_list, save_path=None):
        """
        Create side-by-side comparison of multiple designs

        Parameters:
        -----------
        designs_list : list of dict
            List of design parameters to compare
        save_path : str
            If provided, save figure to this path
        """
        num_designs = len(designs_list)
        fig, axes = plt.subplots(2, num_designs, figsize=(5 * num_designs, 8))

        if num_designs == 1:
            axes = axes.reshape(2, 1)

        for idx, design in enumerate(designs_list):
            L = design["length"]
            N1 = design["n_nose"]
            N2 = design["n_tail"]
            W_w = design["width_weights"]
            H_w = design["height_weights"]

            psi_values = np.linspace(0.001, 0.999, 100)
            x_values = psi_values * L
            widths = np.array([self.calculate_cst_radius(psi, N1, N2, W_w, L) * 2 for psi in psi_values])
            heights = np.array([self.calculate_cst_radius(psi, N1, N2, H_w, L) * 2 for psi in psi_values])

            # Top view
            axes[0, idx].plot(x_values, widths / 2, 'r-', linewidth=2)
            axes[0, idx].plot(x_values, -widths / 2, 'r-', linewidth=2)
            axes[0, idx].fill_between(x_values, -widths / 2, widths / 2, alpha=0.3, color='red')
            axes[0, idx].grid(True, alpha=0.3)
            axes[0, idx].set_title(f'{design["name"]}\nTop View', fontweight='bold')
            axes[0, idx].set_aspect('equal')

            # Side view
            axes[1, idx].plot(x_values, heights / 2, 'b-', linewidth=2)
            axes[1, idx].plot(x_values, -heights / 2, 'b-', linewidth=2)
            axes[1, idx].fill_between(x_values, -heights / 2, heights / 2, alpha=0.3, color='blue')
            axes[1, idx].grid(True, alpha=0.3)
            axes[1, idx].set_title('Side View', fontweight='bold')
            axes[1, idx].set_aspect('equal')
            axes[1, idx].set_xlabel('Length (m)')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"   💾 Saved comparison to: {save_path}")

        return fig

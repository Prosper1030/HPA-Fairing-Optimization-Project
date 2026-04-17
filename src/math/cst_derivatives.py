"""
CST Derivatives - Numerical Differentiation Engine
數值微分引擎：計算 CST 曲線的切線角度
"""
import math


class CSTDerivatives:
    """
    CST 導數計算引擎
    使用有限差分法計算 CST 曲線的切線角度
    """

    @staticmethod
    def cst_class_function(psi, N1, N2):
        """CST 類別函數"""
        if psi <= 0 or psi >= 1:
            return 0.0
        return (psi ** N1) * ((1 - psi) ** N2)

    @staticmethod
    def cst_shape_function(psi, weights):
        """CST 形狀函數（Bernstein 多項式）"""
        if psi <= 0 or psi >= 1:
            return 0.0

        n = len(weights) - 1
        S = 0
        for i in range(len(weights)):
            comb = math.factorial(n) / (math.factorial(i) * math.factorial(n - i))
            bernstein = comb * (psi ** i) * ((1 - psi) ** (n - i))
            S += weights[i] * bernstein
        return S

    @staticmethod
    def cst_radius(psi, N1, N2, weights, length):
        """
        計算 CST 半徑

        Parameters:
        -----------
        psi : float
            歸一化位置 (0 to 1)
        N1 : float
            機頭形狀參數
        N2 : float
            機尾形狀參數
        weights : list
            CST 權重係數
        length : float
            參考長度

        Returns:
        --------
        float : 半徑值
        """
        if psi <= 0 or psi >= 1:
            return 0.0

        C = CSTDerivatives.cst_class_function(psi, N1, N2)
        S = CSTDerivatives.cst_shape_function(psi, weights)
        return C * S * length

    @staticmethod
    def cst_radius_derivative(psi, N1, N2, weights, length, h=1e-6):
        """
        使用有限差分法計算 CST 半徑的導數 dR/d(psi)

        Parameters:
        -----------
        psi : float
            歸一化位置 (0 to 1)
        N1 : float
            機頭形狀參數
        N2 : float
            機尾形狀參數
        weights : list
            CST 權重係數
        length : float
            參考長度
        h : float
            有限差分步長（默認 1e-6）

        Returns:
        --------
        float : dR/d(psi) 導數值
        """
        # 邊界處理
        if psi <= 0:
            # 機頭：使用前向差分
            r1 = CSTDerivatives.cst_radius(psi + h, N1, N2, weights, length)
            r0 = CSTDerivatives.cst_radius(psi, N1, N2, weights, length)
            return (r1 - r0) / h

        elif psi >= 1:
            # 機尾：使用後向差分
            r0 = CSTDerivatives.cst_radius(psi, N1, N2, weights, length)
            r1 = CSTDerivatives.cst_radius(psi - h, N1, N2, weights, length)
            return (r0 - r1) / h

        else:
            # 中間：使用中心差分（更精確）
            r_plus = CSTDerivatives.cst_radius(psi + h, N1, N2, weights, length)
            r_minus = CSTDerivatives.cst_radius(psi - h, N1, N2, weights, length)
            return (r_plus - r_minus) / (2 * h)

    @staticmethod
    def tangent_angle_at_nose(N1, N2, weights):
        """
        計算機頭（psi=0）處的理論切線角度

        當 N1 < 1.0 時（圓頭），切線應垂直於軸線（90度）
        當 N1 >= 1.0 時（錐頭），根據導數計算

        Parameters:
        -----------
        N1 : float
            機頭形狀參數
        N2 : float
            機尾形狀參數
        weights : list
            CST 權重係數

        Returns:
        --------
        float : 角度（度數，0-90 範圍）
        """
        # 圓頭條件：N1 < 1.0
        if N1 < 1.0:
            return 90.0  # 垂直切線

        # 錐頭條件：N1 >= 1.0
        # 使用極限計算
        psi_small = 1e-4  # 接近 0 的小值
        dR_dpsi = CSTDerivatives.cst_radius_derivative(psi_small, N1, N2, weights, 1.0)

        # 切線角度 = arctan(dR/dx)
        # 其中 dx = L * d(psi), 所以 dR/dx = (dR/dpsi) / L
        # 角度應該相對於水平軸
        # 機頭處應該是正角度（上升），所以使用 abs() 是合理的
        angle_rad = math.atan(abs(dR_dpsi))
        angle_deg = math.degrees(angle_rad)

        return min(angle_deg, 90.0)

    @staticmethod
    def tangent_angle(psi, N1, N2, weights, length):
        """
        計算任意位置的切線角度（相對於軸線）

        Parameters:
        -----------
        psi : float
            歸一化位置 (0 to 1)
        N1 : float
            機頭形狀參數
        N2 : float
            機尾形狀參數
        weights : list
            CST 權重係數
        length : float
            參考長度

        Returns:
        --------
        float : 角度（度數）
        """
        # 特殊處理：機頭
        if psi <= 0.001:
            return CSTDerivatives.tangent_angle_at_nose(N1, N2, weights)

        # 特殊處理：機尾
        if psi >= 0.999:
            # 機尾通常收縮，角度接近 0
            psi_tail = 0.999
            dR_dpsi = CSTDerivatives.cst_radius_derivative(psi_tail, N1, N2, weights, length)
            # 保留符號！後段會是負角度
            angle_rad = math.atan(dR_dpsi / length)
            return math.degrees(angle_rad)

        # 一般位置
        dR_dpsi = CSTDerivatives.cst_radius_derivative(psi, N1, N2, weights, length)

        # 切線角度 = arctan(dR/dx)
        # dx = length * d(psi), 所以 dR/dx = dR_dpsi / length
        # 保留符號！前段為正，後段為負（過了最高點）
        angle_rad = math.atan(dR_dpsi / length)
        angle_deg = math.degrees(angle_rad)

        return angle_deg

    @staticmethod
    def compute_tangent_angles_for_section(psi, N1, N2, width_weights, height_weights, length):
        """
        計算截面的四個方向的切線角度

        Parameters:
        -----------
        psi : float
            歸一化位置 (0 to 1)
        N1 : float
            機頭形狀參數
        N2 : float
            機尾形狀參數
        width_weights : list
            寬度方向的 CST 權重
        height_weights : list
            高度方向的 CST 權重
        length : float
            機身長度

        Returns:
        --------
        dict : {
            'right': float,   # 右側角度
            'left': float,    # 左側角度
            'top': float,     # 上側角度
            'bottom': float   # 下側角度
        }
        """
        # 計算寬度和高度方向的切線角度
        angle_width = CSTDerivatives.tangent_angle(psi, N1, N2, width_weights, length)
        angle_height = CSTDerivatives.tangent_angle(psi, N1, N2, height_weights, length)

        return {
            'right': angle_width,
            'left': angle_width,
            'top': angle_height,
            'bottom': angle_height
        }

    @staticmethod
    def curve_slope(x_array, y_array, index):
        """
        在非等距節點上估計一維曲線斜率 dy/dx。

        端點使用一階前/後差分；中間點使用局部二次多項式擬合，
        避免把等距節點的中心差分公式硬套到 cosine spacing。
        """
        n = len(x_array)
        if n < 2:
            return 0.0

        if index <= 0:
            dx = x_array[1] - x_array[0]
            return 0.0 if abs(dx) <= 1e-12 else (y_array[1] - y_array[0]) / dx

        if index >= n - 1:
            dx = x_array[-1] - x_array[-2]
            return 0.0 if abs(dx) <= 1e-12 else (y_array[-1] - y_array[-2]) / dx

        h_s = x_array[index] - x_array[index - 1]
        h_d = x_array[index + 1] - x_array[index]
        if abs(h_s) <= 1e-12 or abs(h_d) <= 1e-12 or abs(h_s + h_d) <= 1e-12:
            dx = x_array[index + 1] - x_array[index - 1]
            return 0.0 if abs(dx) <= 1e-12 else (y_array[index + 1] - y_array[index - 1]) / dx

        return (
            (h_s ** 2) * y_array[index + 1]
            + ((h_d ** 2) - (h_s ** 2)) * y_array[index]
            - (h_d ** 2) * y_array[index - 1]
        ) / (h_s * h_d * (h_d + h_s))

    @staticmethod
    def curve_tangent_angle(x_array, y_array, index, flip_sign=False):
        """從離散曲線斜率換算切線角。"""
        slope = CSTDerivatives.curve_slope(x_array, y_array, index)
        angle = math.degrees(math.atan(slope))
        return -angle if flip_sign else angle

    @staticmethod
    def compute_tangent_angles_for_curves(x_array, width_array, z_upper_array, z_lower_array, index):
        """
        從實際離散曲線直接計算截面四向切線角。
        """
        angle_width = CSTDerivatives.curve_tangent_angle(x_array, width_array, index)
        angle_top = CSTDerivatives.curve_tangent_angle(x_array, z_upper_array, index)
        angle_bottom = CSTDerivatives.curve_tangent_angle(x_array, z_lower_array, index, flip_sign=True)
        return {
            'right': angle_width,
            'left': angle_width,
            'top': angle_top,
            'bottom': angle_bottom,
        }

    @staticmethod
    def compute_asymmetric_tangent_angles(x_array, z_upper_array, z_lower_array, index):
        """
        為非對稱幾何計算上下的切線角度
        直接從z_upper和z_lower曲線的斜率計算

        Parameters:
        -----------
        x_array : array
            X位置陣列
        z_upper_array : array
            上邊界Z位置陣列
        z_lower_array : array
            下邊界Z位置陣列
        index : int
            當前截面索引

        Returns:
        --------
        dict : {
            'top': float,     # 上側角度（從z_upper斜率）
            'bottom': float   # 下側角度（從z_lower斜率）
        }
        """
        return {
            'top': CSTDerivatives.curve_tangent_angle(x_array, z_upper_array, index),
            'bottom': CSTDerivatives.curve_tangent_angle(x_array, z_lower_array, index, flip_sign=True),
        }


# 測試函數
if __name__ == "__main__":
    print("="*80)
    print("CST Derivatives Engine - Test")
    print("="*80)

    # 測試參數
    N1 = 0.5  # 圓頭
    N2 = 1.0
    weights = [0.25, 0.35, 0.30, 0.10]
    length = 2.5

    print(f"\n測試配置：")
    print(f"  N1 (機頭): {N1}")
    print(f"  N2 (機尾): {N2}")
    print(f"  權重: {weights}")
    print(f"  長度: {length} m")

    # 測試機頭角度
    print(f"\n機頭切線角度測試：")
    nose_angle = CSTDerivatives.tangent_angle_at_nose(N1, N2, weights)
    print(f"  psi=0 (機頭): {nose_angle:.2f}° (應為 90° 因為 N1={N1}<1.0)")

    # 測試不同位置的角度
    print(f"\n沿機身的切線角度分佈：")
    psi_values = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0]
    for psi in psi_values:
        angle = CSTDerivatives.tangent_angle(psi, N1, N2, weights, length)
        radius = CSTDerivatives.cst_radius(psi, N1, N2, weights, length)
        print(f"  psi={psi:.1f}: R={radius:.4f}m, 角度={angle:.2f}°")

    # 測試錐頭情況
    print(f"\n錐頭情況測試 (N1=1.5)：")
    N1_cone = 1.5
    nose_angle_cone = CSTDerivatives.tangent_angle_at_nose(N1_cone, N2, weights)
    print(f"  psi=0 (機頭): {nose_angle_cone:.2f}° (N1={N1_cone}>=1.0)")

    print("\n" + "="*80)
    print("✅ 測試完成！")
    print("="*80)

"""
Section Distribution - Advanced Grid Generation
截面分佈策略：全餘弦分佈與防呆機制
"""
import math


class SectionDistribution:
    """
    截面分佈生成器
    提供多種分佈策略，重點為全餘弦分佈
    """

    @staticmethod
    def cosine_full(num_sections, min_spacing=0.001):
        """
        全餘弦分佈（Full Cosine Distribution）
        密集分佈在機頭和機尾，中間稀疏

        Parameters:
        -----------
        num_sections : int
            截面總數
        min_spacing : float
            最小間距限制（防止截面重疊）

        Returns:
        --------
        list : psi 值列表 (0 to 1)
        """
        if num_sections < 2:
            raise ValueError("截面數量必須 >= 2")

        n = num_sections
        psi_values = []

        for i in range(n):
            # 餘弦分佈公式：psi = 0.5 * (1 - cos(π * i / (n-1)))
            # 這會在 0 和 1 兩端密集分佈
            psi = 0.5 * (1.0 - math.cos(math.pi * i / (n - 1)))
            psi_values.append(psi)

        # 防呆機制：檢查最小間距
        psi_validated = SectionDistribution._enforce_min_spacing(
            psi_values, min_spacing
        )

        return psi_validated

    @staticmethod
    def cosine_nose_only(num_sections, min_spacing=0.001):
        """
        機頭密集餘弦分佈
        僅在機頭（psi=0）處密集

        Parameters:
        -----------
        num_sections : int
            截面總數
        min_spacing : float
            最小間距限制

        Returns:
        --------
        list : psi 值列表 (0 to 1)
        """
        if num_sections < 2:
            raise ValueError("截面數量必須 >= 2")

        n = num_sections
        psi_values = []

        for i in range(n):
            # 單側餘弦：psi = 1 - cos(0.5π * i / (n-1))
            psi = 1.0 - math.cos(0.5 * math.pi * i / (n - 1))
            psi_values.append(psi)

        psi_validated = SectionDistribution._enforce_min_spacing(
            psi_values, min_spacing
        )

        return psi_validated

    @staticmethod
    def cosine_tail_only(num_sections, min_spacing=0.001):
        """
        機尾密集餘弦分佈
        僅在機尾（psi=1）處密集

        Parameters:
        -----------
        num_sections : int
            截面總數
        min_spacing : float
            最小間距限制

        Returns:
        --------
        list : psi 值列表 (0 to 1)
        """
        if num_sections < 2:
            raise ValueError("截面數量必須 >= 2")

        n = num_sections
        psi_values = []

        for i in range(n):
            # 單側餘弦（尾部）：psi = sin(0.5π * i / (n-1))
            psi = math.sin(0.5 * math.pi * i / (n - 1))
            psi_values.append(psi)

        psi_validated = SectionDistribution._enforce_min_spacing(
            psi_values, min_spacing
        )

        return psi_validated

    @staticmethod
    def uniform(num_sections):
        """
        均勻分佈（線性等距）

        Parameters:
        -----------
        num_sections : int
            截面總數

        Returns:
        --------
        list : psi 值列表 (0 to 1)
        """
        if num_sections < 2:
            raise ValueError("截面數量必須 >= 2")

        return [i / (num_sections - 1) for i in range(num_sections)]

    @staticmethod
    def _enforce_min_spacing(psi_values, min_spacing):
        """
        強制執行最小間距限制
        防止餘弦分佈在端點處截面過於密集導致重疊

        Parameters:
        -----------
        psi_values : list
            原始 psi 值
        min_spacing : float
            最小間距（歸一化單位）

        Returns:
        --------
        list : 修正後的 psi 值
        """
        if min_spacing <= 0:
            return psi_values

        validated = [psi_values[0]]  # 第一個點保持不變（psi=0）

        for i in range(1, len(psi_values)):
            current_psi = psi_values[i]
            prev_psi = validated[-1]

            # 檢查間距
            spacing = current_psi - prev_psi

            if spacing < min_spacing:
                # 強制最小間距
                current_psi = prev_psi + min_spacing

            validated.append(current_psi)

        # 確保最後一個點為 1.0
        if validated[-1] > 1.0:
            # 重新縮放以確保端點正確
            scale_factor = 1.0 / validated[-1]
            validated = [psi * scale_factor for psi in validated]

        return validated

    @staticmethod
    def analyze_distribution(psi_values):
        """
        分析分佈的統計特性

        Parameters:
        -----------
        psi_values : list
            psi 值列表

        Returns:
        --------
        dict : 統計資訊
        """
        if len(psi_values) < 2:
            return {}

        spacings = []
        for i in range(1, len(psi_values)):
            spacing = psi_values[i] - psi_values[i-1]
            spacings.append(spacing)

        return {
            'num_sections': len(psi_values),
            'min_spacing': min(spacings),
            'max_spacing': max(spacings),
            'avg_spacing': sum(spacings) / len(spacings),
            'spacing_ratio': max(spacings) / min(spacings) if min(spacings) > 0 else float('inf')
        }


# 測試函數
if __name__ == "__main__":
    print("="*80)
    print("Section Distribution - Test")
    print("="*80)

    num_sections = 40
    min_spacing = 0.001

    print(f"\n測試配置：")
    print(f"  截面數量: {num_sections}")
    print(f"  最小間距: {min_spacing}")

    # 測試全餘弦分佈
    print(f"\n【1】全餘弦分佈（推薦用於阻力分析）：")
    psi_cosine = SectionDistribution.cosine_full(num_sections, min_spacing)
    stats_cosine = SectionDistribution.analyze_distribution(psi_cosine)

    print(f"  前5個截面位置: {[f'{p:.6f}' for p in psi_cosine[:5]]}")
    print(f"  後5個截面位置: {[f'{p:.6f}' for p in psi_cosine[-5:]]}")
    print(f"\n  統計資訊：")
    print(f"    最小間距: {stats_cosine['min_spacing']:.6f}")
    print(f"    最大間距: {stats_cosine['max_spacing']:.6f}")
    print(f"    平均間距: {stats_cosine['avg_spacing']:.6f}")
    print(f"    間距比率: {stats_cosine['spacing_ratio']:.2f}x")

    # 測試機頭密集分佈
    print(f"\n【2】機頭密集分佈：")
    psi_nose = SectionDistribution.cosine_nose_only(num_sections, min_spacing)
    stats_nose = SectionDistribution.analyze_distribution(psi_nose)

    print(f"  前5個截面位置: {[f'{p:.6f}' for p in psi_nose[:5]]}")
    print(f"  統計：最小={stats_nose['min_spacing']:.6f}, 比率={stats_nose['spacing_ratio']:.2f}x")

    # 測試均勻分佈（對比）
    print(f"\n【3】均勻分佈（對比）：")
    psi_uniform = SectionDistribution.uniform(num_sections)
    stats_uniform = SectionDistribution.analyze_distribution(psi_uniform)

    print(f"  前5個截面位置: {[f'{p:.6f}' for p in psi_uniform[:5]]}")
    print(f"  統計：最小={stats_uniform['min_spacing']:.6f}, 比率={stats_uniform['spacing_ratio']:.2f}x")

    # 視覺化比較（ASCII）
    print(f"\n【4】分佈視覺化（前10個截面）：")
    print(f"  {'Index':<6} | {'Uniform':<10} | {'Cosine':<10} | {'Delta':<10}")
    print(f"  {'-'*50}")
    for i in range(min(10, num_sections)):
        delta = psi_cosine[i] - psi_uniform[i]
        print(f"  {i:<6} | {psi_uniform[i]:<10.6f} | {psi_cosine[i]:<10.6f} | {delta:+10.6f}")

    print("\n" + "="*80)
    print("✅ 測試完成！")
    print("💡 結論：全餘弦分佈在機頭的截面密度是均勻分佈的 {:.1f}x".format(
        stats_cosine['spacing_ratio'] / stats_uniform['spacing_ratio']
    ))
    print("="*80)

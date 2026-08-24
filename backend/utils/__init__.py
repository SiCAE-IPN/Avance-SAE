__all__ = []

try:
	from backend.utils.acuse_pdf import (
		TEXTO_ACUSE_DEFAULT,
		generar_acuse_matricula_pdf,
		generar_acuse_matricula_pdf_en_memoria,
		generar_oficio_conclusion_pdf_en_memoria,
	)

	__all__.extend(
		[
			"TEXTO_ACUSE_DEFAULT",
			"generar_acuse_matricula_pdf",
			"generar_acuse_matricula_pdf_en_memoria",
			"generar_oficio_conclusion_pdf_en_memoria",
		]
	)
except ModuleNotFoundError:
	# Permite que el backend arranque aunque falten dependencias opcionales de acuses.
	pass

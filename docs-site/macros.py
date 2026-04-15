"""MkDocs macros plugin — exposes extra.vars as Jinja2 variables."""


def define_env(env):
    """Hook for mkdocs-macros-plugin. Makes extra.vars available as {{ var_name }}."""
    vars_dict = env.conf.get("extra", {}).get("vars", {})
    for key, value in vars_dict.items():
        env.variables[key] = value

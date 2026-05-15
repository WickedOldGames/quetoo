/*
 * Copyright(c) 1997-2001 id Software, Inc.
 * Copyright(c) 2002 The Quakeforge Project.
 * Copyright(c) 2006 Quetoo.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 *
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */

#include "cg_local.h"

#include "MeshViewController.h"

#define _Class _MeshViewController

#pragma mark - Internal helpers

static MeshConfig identity = { .scale = 1.f };

/**
 * @brief Parses a mesh config file into transform components.
 */
static void ParseMeshConfig(const char *path, MeshConfig *cfg) {

  cfg->translate = Vec3_Zero();
  cfg->rotate = Vec3_Zero();
  cfg->scale = 1.f;
  cfg->muzzle = Vec3_Zero();

  void *buf;
  if (cgi.LoadFile(path, &buf) == -1) {
    return;
  }

  parser_t parser = Parse_Init((const char *) buf, PARSER_DEFAULT);
  char token[MAX_STRING_CHARS];

  while (true) {

    if (!Parse_Token(&parser, PARSE_DEFAULT, token, sizeof(token))) {
      break;
    }

    const parse_flags_t flags = PARSE_DEFAULT | PARSE_WITHIN_QUOTES | PARSE_NO_WRAP;

    if (!g_strcmp0(token, "translate")) {
      Parse_Primitive(&parser, flags, PARSE_FLOAT, cfg->translate.xyz, 3);
    } else if (!g_strcmp0(token, "rotate")) {
      Parse_Primitive(&parser, flags, PARSE_FLOAT, cfg->rotate.xyz, 3);
    } else if (!g_strcmp0(token, "scale")) {
      Parse_Primitive(&parser, flags, PARSE_FLOAT, &cfg->scale, 1);
    } else if (!g_strcmp0(token, "muzzle")) {
      Parse_Primitive(&parser, flags, PARSE_FLOAT, cfg->muzzle.xyz, 3);
    }
  }

  cgi.FreeFile(buf);
}

/**
 * @brief Builds a mat4_t transform from raw config components.
 */
static mat4_t MeshConfigTransform(const MeshConfig *cfg) {

  mat4_t m = Mat4_Identity();
  m = Mat4_ConcatTranslation(m, cfg->translate);
  m = Mat4_ConcatRotation3(m, cfg->rotate);
  m = Mat4_ConcatScale(m, cfg->scale);
  return m;
}

#pragma mark - Delegates

/**
 * @brief TextViewDelegate callback — parse text and reapply transform live.
 */
static void didEndEditing(TextView *textView) {

  MeshViewController *this = textView->delegate.self;

  if (!this->model) {
    return;
  }

  const char *text = textView->attributedText->string.chars ?: "";

  if (textView == this->worldTranslate) {
    sscanf(text, "%f %f %f", &this->world.translate.x, &this->world.translate.y, &this->world.translate.z);
    this->model->mesh->config.world.transform = MeshConfigTransform(&this->world);
  } else if (textView == this->worldRotate) {
    sscanf(text, "%f %f %f", &this->world.rotate.x, &this->world.rotate.y, &this->world.rotate.z);
    this->model->mesh->config.world.transform = MeshConfigTransform(&this->world);
  } else if (textView == this->worldScale) {
    sscanf(text, "%f", &this->world.scale);
    this->model->mesh->config.world.transform = MeshConfigTransform(&this->world);
  } else if (textView == this->linkTranslate) {
    sscanf(text, "%f %f %f", &this->link.translate.x, &this->link.translate.y, &this->link.translate.z);
    this->model->mesh->config.link.transform = MeshConfigTransform(&this->link);
  } else if (textView == this->linkRotate) {
    sscanf(text, "%f %f %f", &this->link.rotate.x, &this->link.rotate.y, &this->link.rotate.z);
    this->model->mesh->config.link.transform = MeshConfigTransform(&this->link);
  } else if (textView == this->linkScale) {
    sscanf(text, "%f", &this->link.scale);
    this->model->mesh->config.link.transform = MeshConfigTransform(&this->link);
  } else if (textView == this->viewTranslate) {
    sscanf(text, "%f %f %f", &this->view.translate.x, &this->view.translate.y, &this->view.translate.z);
    this->model->mesh->config.view.transform = MeshConfigTransform(&this->view);
  } else if (textView == this->viewRotate) {
    sscanf(text, "%f %f %f", &this->view.rotate.x, &this->view.rotate.y, &this->view.rotate.z);
    this->model->mesh->config.view.transform = MeshConfigTransform(&this->view);
  } else if (textView == this->viewScale) {
    sscanf(text, "%f", &this->view.scale);
    this->model->mesh->config.view.transform = MeshConfigTransform(&this->view);
  } else if (textView == this->viewMuzzle) {
    sscanf(text, "%f %f %f", &this->view.muzzle.x, &this->view.muzzle.y, &this->view.muzzle.z);
    this->model->mesh->config.view.muzzle = this->view.muzzle;
  } else {
    Cg_Debug("Unknown text view %p\n", (void *) textView);
  }
}

#pragma mark - ViewController

/**
 * @see ViewController::loadView(ViewController *)
 */
static void loadView(ViewController *self) {

  super(ViewController, self, loadView);

  MeshViewController *this = (MeshViewController *) self;

  Outlet outlets[] = MakeOutlets(
    MakeOutlet("worldTranslate", &this->worldTranslate),
    MakeOutlet("worldRotate",    &this->worldRotate),
    MakeOutlet("worldScale",     &this->worldScale),
    MakeOutlet("linkTranslate",  &this->linkTranslate),
    MakeOutlet("linkRotate",     &this->linkRotate),
    MakeOutlet("linkScale",      &this->linkScale),
    MakeOutlet("viewTranslate",  &this->viewTranslate),
    MakeOutlet("viewRotate",     &this->viewRotate),
    MakeOutlet("viewScale",      &this->viewScale),
    MakeOutlet("viewMuzzle",     &this->viewMuzzle)
  );

  $(self->view, awakeWithResourceName, "ui/editor/MeshViewController.json");
  $(self->view, resolve, outlets);

  self->view->stylesheet = $$(Stylesheet, stylesheetWithResourceName, "ui/editor/MeshViewController.css");

  TextView *textViews[] = {
    this->worldTranslate, this->worldRotate, this->worldScale,
    this->linkTranslate,  this->linkRotate,  this->linkScale,
    this->viewTranslate,  this->viewRotate,  this->viewScale, this->viewMuzzle,
  };

  for (size_t i = 0; i < lengthof(textViews); i++) {
    textViews[i]->delegate.self = self;
    textViews[i]->delegate.didEndEditing = didEndEditing;
  }
}

/**
 * @see ViewController::viewWillAppear(ViewController *)
 */
static void viewWillAppear(ViewController *self) {

  MeshViewController *this = (MeshViewController *) self;

  r_model_t *model = NULL;

  if (cg_editor.selected > 0) {
    const cg_editor_entity_t *edit = &cg_editor.entities[cg_editor.selected];
    if (edit->model && IS_MESH_MODEL(edit->model)) {
      model = (r_model_t *) edit->model;
    }
  }

  $(this, setModel, model);

  super(ViewController, self, viewWillAppear);
}

#pragma mark - MeshViewController

/**
 * @fn MeshViewController *MeshViewController::init(MeshViewController *self)
 * @memberof MeshViewController
 */
static MeshViewController *init(MeshViewController *self) {
  return (MeshViewController *) super(ViewController, self, init);
}

/**
 * @fn void MeshViewController::setModel(MeshViewController *self, r_model_t *model)
 * @memberof MeshViewController
 */
static void setModel(MeshViewController *self, r_model_t *model) {
  char path[MAX_QPATH];

  self->model = model;

  if (self->model) {
    Dirname(self->model->media.name, path);
  }

  ParseMeshConfig(self->model ? va("%s/world.cfg", path) : "", &self->world);
  ParseMeshConfig(self->model ? va("%s/link.cfg",  path) : "", &self->link);
  ParseMeshConfig(self->model ? va("%s/view.cfg",  path) : "", &self->view);

  $(self->worldTranslate, setAttributedText, va("%g %g %g", self->world.translate.x, self->world.translate.y, self->world.translate.z));
  $(self->worldRotate,    setAttributedText, va("%g %g %g", self->world.rotate.x,    self->world.rotate.y,    self->world.rotate.z));
  $(self->worldScale,     setAttributedText, va("%g",       self->world.scale));

  $(self->linkTranslate,  setAttributedText, va("%g %g %g", self->link.translate.x,  self->link.translate.y,  self->link.translate.z));
  $(self->linkRotate,     setAttributedText, va("%g %g %g", self->link.rotate.x,     self->link.rotate.y,     self->link.rotate.z));
  $(self->linkScale,      setAttributedText, va("%g",       self->link.scale));

  $(self->viewTranslate,  setAttributedText, va("%g %g %g", self->view.translate.x,  self->view.translate.y,  self->view.translate.z));
  $(self->viewRotate,     setAttributedText, va("%g %g %g", self->view.rotate.x,     self->view.rotate.y,     self->view.rotate.z));
  $(self->viewScale,      setAttributedText, va("%g",       self->view.scale));
  $(self->viewMuzzle,     setAttributedText, va("%g %g %g", self->view.muzzle.x,     self->view.muzzle.y,     self->view.muzzle.z));
}

/**
 * @fn void MeshViewController::save(MeshViewController *self)
 * @memberof MeshViewController
 */
static void save(MeshViewController *self) {

  if (!self->model) {
    return;
  }

  char dir[MAX_QPATH];
  Dirname(self->model->media.name, dir);

  typedef struct {
    const char *name;
    const MeshConfig *cfg;
  } MeshConfigFile;

  const MeshConfigFile files[] = {
    { "world.cfg", &self->world },
    { "link.cfg",  &self->link },
    { "view.cfg",  &self->view },
  };

  for (size_t c = 0; c < lengthof(files); c++) {

    const MeshConfigFile *f = &files[c];

    if (!memcmp(&identity, f->cfg, sizeof(identity))) {
      continue;
    }

    const char *path = va("%s/%s", dir, f->name);
    file_t *file = cgi.OpenFileWrite(path);
    if (!file) {
      Cg_Warn("Failed to write %s\n", path);
      continue;
    }

    char line[MAX_STRING_CHARS];
    size_t len;

    if (!Vec3_Equal(f->cfg->translate, Vec3_Zero())) {
      len = (size_t) g_snprintf(line, sizeof(line), "translate %g %g %g\n",
          f->cfg->translate.x, f->cfg->translate.y, f->cfg->translate.z);
      cgi.WriteFile(file, line, 1, len);
    }

    if (!Vec3_Equal(f->cfg->rotate, Vec3_Zero())) {
      len = (size_t) g_snprintf(line, sizeof(line), "rotate %g %g %g\n",
          f->cfg->rotate.x, f->cfg->rotate.y, f->cfg->rotate.z);
      cgi.WriteFile(file, line, 1, len);
    }

    if (f->cfg->scale != 1.f) {
      len = (size_t) g_snprintf(line, sizeof(line), "scale %g\n", f->cfg->scale);
      cgi.WriteFile(file, line, 1, len);
    }

    if (!Vec3_Equal(f->cfg->muzzle, Vec3_Zero())) {
      len = (size_t) g_snprintf(line, sizeof(line), "muzzle %g %g %g\n",
          f->cfg->muzzle.x, f->cfg->muzzle.y, f->cfg->muzzle.z);
      cgi.WriteFile(file, line, 1, len);
    }

    cgi.CloseFile(file);
    Cg_Debug("Wrote %s\n", path);
  }
}

#pragma mark - Class lifecycle

/**
 * @see Class::initialize(Class *)
 */
static void initialize(Class *clazz) {

  ((ViewControllerInterface *) clazz->interface)->loadView = loadView;
  ((ViewControllerInterface *) clazz->interface)->viewWillAppear = viewWillAppear;

  ((MeshViewControllerInterface *) clazz->interface)->init = init;
  ((MeshViewControllerInterface *) clazz->interface)->setModel = setModel;
  ((MeshViewControllerInterface *) clazz->interface)->save = save;
}

/**
 * @fn Class *MeshViewController::_MeshViewController(void)
 * @memberof MeshViewController
 */
Class *_MeshViewController(void) {
  static Class *clazz;
  static Once once;

  do_once(&once, {
    clazz = _initialize(&(const ClassDef) {
      .name = "MeshViewController",
      .superclass = _ViewController(),
      .instanceSize = sizeof(MeshViewController),
      .interfaceOffset = offsetof(MeshViewController, interface),
      .interfaceSize = sizeof(MeshViewControllerInterface),
      .initialize = initialize,
    });
  });

  return clazz;
}

#undef _Class
